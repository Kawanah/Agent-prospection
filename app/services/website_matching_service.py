"""
Service de validation du matching lead ↔ site web.

Objectif : éviter de générer un audit ou un email sur un site qui n'appartient
pas réellement au prospect.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

from app.models.lead import Lead, WebsiteMatchStatus


_STOPWORDS = {
    "le",
    "la",
    "les",
    "de",
    "du",
    "des",
    "d",
    "un",
    "une",
    "et",
    "a",
    "au",
    "aux",
    "en",
    "chez",
    "monsieur",
    "madame",
    "mr",
    "mme",
    "patrick",
}

_SUSPICIOUS_PROVIDER_TERMS = {
    "web",
    "studio",
    "agency",
    "agence",
    "creation",
    "crea",
    "ahcrea",
    "design",
    "communication",
    "marketing",
    "dev",
    "digital",
}

_ACTIVITY_TERMS = {
    "hotel": {"hotel", "hôtel", "chambre", "séjour", "sejour"},
    "camping": {"camping", "emplacement", "mobil", "vacances", "campeur"},
    "gite": {"gite", "gîte", "meublé", "meuble", "location", "séjour", "sejour"},
    "chambre_hotes": {"chambre", "hôtes", "hotes", "maison", "séjour", "sejour"},
    "residence": {"résidence", "residence", "appartement", "séjour", "sejour"},
    "activite": {"activité", "activite", "loisir", "club", "sport", "inscription"},
}


@dataclass
class WebsiteMatchResult:
    status: WebsiteMatchStatus
    confidence: int
    source: str
    reasons: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "reasons": self.reasons,
            "penalties": self.penalties,
        }


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower()


def _tokens(value: str | None) -> set[str]:
    normalized = _normalize(value)
    raw = re.findall(r"[a-z0-9]{3,}", normalized)
    return {token for token in raw if token not in _STOPWORDS}


def _domain(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc or parsed.path.split("/")[0]
    return host.lower().removeprefix("www.")


def evaluate_website_match(
    lead: Lead,
    website_url: str | None,
    source: str = "unknown",
    page_text: str | None = None,
) -> WebsiteMatchResult:
    """Calcule un score de confiance lisible pour le site proposé."""
    if not website_url:
        return WebsiteMatchResult(
            status=WebsiteMatchStatus.NO_SITE,
            confidence=0,
            source=source,
            reasons=["Aucune URL de site associée au lead"],
        )

    domain = _domain(website_url)
    domain_compact = re.sub(r"[^a-z0-9]", "", _normalize(domain))
    text = _normalize(page_text)
    name_tokens = _tokens(lead.name)
    city_tokens = _tokens(lead.city)
    activity_tokens = _ACTIVITY_TERMS.get(
        lead.lead_type.value if lead.lead_type else "other", set()
    )

    score = 0
    reasons: list[str] = []
    penalties: list[str] = []

    if source == "google_places":
        score += 35
        reasons.append("Site fourni par Google Places")
    elif source in {"manual", "validated_manual"}:
        score += 40
        reasons.append("Site validé manuellement")
    elif source in {"csv_import", "source_file", "data.gouv.fr"}:
        score += 15
        reasons.append("Site présent dans la source d'import")
    elif source in {"web_search", "duckduckgo"}:
        score += 10
        reasons.append("Site trouvé par recherche web")

    matched_name_tokens = [token for token in name_tokens if token in domain_compact]
    if matched_name_tokens:
        score += min(35, 18 + len(matched_name_tokens) * 7)
        reasons.append(
            f"Nom retrouvé dans le domaine : {', '.join(matched_name_tokens)}"
        )
    elif page_text and any(token in text for token in name_tokens):
        score += 25
        reasons.append("Nom du lead retrouvé dans la page")
    else:
        score -= 35
        penalties.append("Nom du lead absent du domaine et des preuves disponibles")

    if city_tokens:
        if any(token in domain_compact for token in city_tokens):
            score += 18
            reasons.append("Ville retrouvée dans le domaine")
        elif page_text and any(token in text for token in city_tokens):
            score += 15
            reasons.append("Ville retrouvée dans la page")
        else:
            score -= 15
            penalties.append("Ville non retrouvée")

    if page_text and activity_tokens:
        if any(_normalize(term) in text for term in activity_tokens):
            score += 15
            reasons.append("Activité cohérente retrouvée dans la page")
        else:
            score -= 15
            penalties.append("Activité non retrouvée dans la page")

    suspicious_terms = [
        term for term in _SUSPICIOUS_PROVIDER_TERMS if term in domain_compact
    ]
    if suspicious_terms and not matched_name_tokens:
        score -= 30
        penalties.append(
            f"Domaine ressemblant à un prestataire tiers : {', '.join(suspicious_terms[:3])}"
        )

    score = max(0, min(100, score))

    if score >= 80:
        status = WebsiteMatchStatus.VERIFIED
    elif score >= 50:
        status = WebsiteMatchStatus.NEEDS_REVIEW
    else:
        status = WebsiteMatchStatus.REJECTED

    return WebsiteMatchResult(
        status=status,
        confidence=score,
        source=source,
        reasons=reasons,
        penalties=penalties,
    )


def apply_website_match(
    lead: Lead,
    website_url: str | None = None,
    source: str = "unknown",
    page_text: str | None = None,
) -> WebsiteMatchResult:
    """Évalue et écrit le résultat sur le lead."""
    result = evaluate_website_match(
        lead, website_url or lead.website, source, page_text
    )
    lead.website_match_status = result.status
    lead.website_match_confidence = result.confidence
    lead.website_match_source = result.source
    lead.website_match_reasons = result.as_dict()
    if result.status == WebsiteMatchStatus.VERIFIED:
        lead.website_validated_at = datetime.utcnow()
    return result
