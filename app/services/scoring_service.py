"""
Service de Scoring et Priorisation des leads.
Analyse automatiquement les sites web et calcule des scores de priorité.

Critères d'analyse :
- Qualité du site web (design, modernité, responsive)
- SEO basique (balises title, meta, h1, etc.)
- GEO (Generative Engine Optimization) - optimisation pour les IA
- Mobile-friendly
- Taille de l'établissement (capacité, chambres)
"""

import re
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.lead import Lead, LeadStatus, LeadType
from app.config import get_settings
from app.models.lead import WebsiteMatchStatus
from app.services.website_matching_service import apply_website_match

settings = get_settings()


@dataclass
class WebsiteAnalysisResult:
    """Résultat de l'analyse d'un site web."""

    success: bool = False
    url: str = ""

    # Qualité générale (0-100)
    quality_score: int = 0

    # SEO (0-100)
    seo_score: int = 0
    has_title: bool = False
    has_meta_description: bool = False
    has_h1: bool = False
    has_alt_images: bool = False

    # GEO - Generative Engine Optimization (0-100)
    geo_score: int = 0
    has_structured_data: bool = False  # Schema.org / JSON-LD
    has_faq_schema: bool = False  # FAQ structurée
    has_local_business: bool = False  # LocalBusiness schema
    has_clear_contact: bool = False  # Infos contact visibles
    content_richness: int = 0  # Richesse du contenu (0-100)

    # Mobile
    is_mobile_friendly: bool = False
    has_viewport_meta: bool = False

    # Fonctionnalités concrètes (audit pour argumentaire commercial)
    has_contact_form: bool = False
    has_reservation: bool = False  # Réservation en direct (formulaire ou moteur)
    has_booking_system: bool = False  # Alias de has_reservation (compat lead)
    booking_platforms: list = field(default_factory=list)  # Moteurs détectés
    has_embedded_reviews: bool = False  # Avis clients affichés sur le site
    has_map: bool = False  # Carte d'accès / plan de localisation
    has_photo_gallery: bool = False  # Galerie / mise en valeur photo
    design_dated: bool = False  # Design visuellement daté
    audit_findings: list = field(default_factory=list)  # Constats concrets (FR)

    # Technique
    uses_https: bool = False
    load_time_ms: Optional[int] = None

    # Erreur
    error: Optional[str] = None


class WebsiteAnalyzer:
    """Analyseur de sites web pour le scoring."""

    # Indicateurs d'un site moderne
    MODERN_INDICATORS = [
        "tailwind",
        "bootstrap",
        "react",
        "vue",
        "angular",
        "webp",
        "lazy",
        "async",
        "defer",
        "preload",
    ]

    # Indicateurs d'un vieux site
    OLD_SITE_INDICATORS = [
        "table border=",
        "font face=",
        "bgcolor=",
        "frameset",
        "marquee",
        "blink",
        "<center>",
        "frontpage",
    ]

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            },
        )

    async def close(self):
        """Ferme le client HTTP."""
        await self.client.aclose()

    def _normalize_url(self, url: str) -> str:
        """Normalise une URL pour s'assurer qu'elle est valide."""
        if not url:
            return url

        url = url.strip()

        # Supprimer le / au début si présent
        if url.startswith("/"):
            url = url[1:]

        # Ajouter https:// si pas de protocole (conserver http:// si explicitement fourni)
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url

    async def analyze(self, url: str) -> WebsiteAnalysisResult:
        """Analyse complète d'un site web."""
        # Normaliser l'URL
        url = self._normalize_url(url)
        result = WebsiteAnalysisResult(url=url)

        # Vérifier HTTPS
        result.uses_https = url.startswith("https://")

        try:
            # Mesurer le temps de chargement
            start_time = asyncio.get_event_loop().time()
            response = await self.client.get(url)
            end_time = asyncio.get_event_loop().time()

            result.load_time_ms = int((end_time - start_time) * 1000)

            # Accepter 200 et les codes de succès courants.
            # 403/429 = le site existe mais bloque les bots → on le marque quand même présent.
            if response.status_code >= 500:
                result.error = f"HTTP {response.status_code}"
                return result

            # Si le site est accessible (même avec un code 4xx type anti-bot),
            # on tente quand même d'analyser le contenu si on en a un.
            html = response.text if response.text else ""
            if not html and response.status_code not in (200, 201):
                # Pas de contenu analysable mais le site répond → il existe
                result.success = True
                return result
            soup = BeautifulSoup(html, "lxml")

            # Analyser les différents aspects
            self._analyze_seo(result, soup, html)
            self._analyze_geo(result, soup, html)
            self._analyze_mobile(result, soup, html)
            self._analyze_quality(result, soup, html)
            self._analyze_features(result, soup, html)

            result.success = True

        except httpx.TimeoutException:
            result.error = "Timeout - site trop lent"
            result.quality_score = 20  # Site lent = mauvais score
        except (httpx.ConnectError, httpx.SSLError) as e:
            # Erreur SSL ou DNS en https:// → retenter en http://
            if url.startswith("https://"):
                http_url = "http://" + url[8:]
                logger.info(f"Fallback HTTP pour {url}")
                try:
                    response = await self.client.get(http_url)
                    if response.status_code < 500:
                        html = response.text or ""
                        result.url = http_url
                        result.uses_https = False
                        if html:
                            soup = BeautifulSoup(html, "lxml")
                            self._analyze_seo(result, soup, html)
                            self._analyze_geo(result, soup, html)
                            self._analyze_mobile(result, soup, html)
                            self._analyze_quality(result, soup, html)
                            self._analyze_features(result, soup, html)
                        result.success = True
                        return result
                except Exception:
                    pass
            result.error = str(e)
            logger.warning(f"Site inaccessible {url}: {e}")
        except Exception as e:
            result.error = str(e)
            logger.error(f"Erreur analyse {url}: {e}")

        return result

    def _analyze_seo(
        self, result: WebsiteAnalysisResult, soup: BeautifulSoup, html: str
    ):
        """Analyse SEO basique."""
        score = 0

        # Title
        title = soup.find("title")
        if title and title.text.strip():
            result.has_title = True
            score += 25
            # Bonus si le titre est optimisé (entre 30 et 60 caractères)
            if 30 <= len(title.text.strip()) <= 60:
                score += 5

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content", "").strip():
            result.has_meta_description = True
            score += 25
            # Bonus si la description est optimisée (entre 120 et 160 caractères)
            if 120 <= len(meta_desc.get("content", "")) <= 160:
                score += 5

        # H1
        h1 = soup.find("h1")
        if h1 and h1.text.strip():
            result.has_h1 = True
            score += 20

        # Images avec alt
        images = soup.find_all("img")
        if images:
            images_with_alt = [img for img in images if img.get("alt", "").strip()]
            ratio = len(images_with_alt) / len(images) if images else 0
            result.has_alt_images = ratio > 0.5
            score += int(20 * ratio)
        else:
            score += 10  # Pas d'images = pas de pénalité

        result.seo_score = min(score, 100)

    def _analyze_geo(
        self, result: WebsiteAnalysisResult, soup: BeautifulSoup, html: str
    ):
        """
        Analyse GEO (Generative Engine Optimization).
        Évalue si le site est optimisé pour les moteurs de réponse IA
        (ChatGPT, Perplexity, Claude, Google AI Overviews, etc.)
        """
        score = 0
        html_lower = html.lower()

        # 1. Données structurées Schema.org / JSON-LD (très important pour les IA)
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        if json_ld_scripts:
            result.has_structured_data = True
            score += 25

            # Vérifier les types de schema
            for script in json_ld_scripts:
                script_text = script.string or ""
                script_lower = script_text.lower()

                # LocalBusiness ou Hotel schema (très pertinent pour l'hospitalité)
                if any(
                    t in script_lower
                    for t in ["localbusiness", "hotel", "lodgingbusiness", "campground"]
                ):
                    result.has_local_business = True
                    score += 15

                # FAQ schema (les IA adorent les FAQ)
                if "faqpage" in script_lower or "question" in script_lower:
                    result.has_faq_schema = True
                    score += 10

        # 2. Microdonnées Schema.org (alternative au JSON-LD)
        if not result.has_structured_data:
            microdata = soup.find_all(attrs={"itemtype": True})
            if microdata:
                result.has_structured_data = True
                score += 15

        # 3. Informations de contact claires et structurées
        contact_indicators = [
            ("tel:", 5),  # Liens téléphone
            ("mailto:", 5),  # Liens email
            ("address", 3),  # Balises adresse
            ('itemprop="telephone"', 5),
            ('itemprop="email"', 5),
            ('itemprop="address"', 5),
        ]

        contact_score = 0
        for indicator, points in contact_indicators:
            if indicator in html_lower:
                contact_score += points

        if contact_score >= 10:
            result.has_clear_contact = True
            score += 15

        # 4. Richesse du contenu (important pour que les IA comprennent l'établissement)
        content_score = 0

        # Présence de paragraphes descriptifs
        paragraphs = soup.find_all("p")
        text_content = " ".join(p.get_text() for p in paragraphs)
        word_count = len(text_content.split())

        if word_count > 500:
            content_score += 30
        elif word_count > 200:
            content_score += 20
        elif word_count > 100:
            content_score += 10

        # Listes (services, équipements) - structure que les IA comprennent bien
        lists = soup.find_all(["ul", "ol"])
        list_items = sum(len(lst.find_all("li")) for lst in lists)
        if list_items > 10:
            content_score += 20
        elif list_items > 5:
            content_score += 10

        # Sections bien structurées (h2, h3)
        headings = soup.find_all(["h2", "h3"])
        if len(headings) >= 5:
            content_score += 20
        elif len(headings) >= 3:
            content_score += 10

        # FAQ visible (même sans schema)
        faq_keywords = [
            "faq",
            "questions fréquentes",
            "questions-réponses",
            "frequently asked",
        ]
        if any(kw in html_lower for kw in faq_keywords):
            content_score += 20

        result.content_richness = min(content_score, 100)
        score += int(content_score * 0.35)  # 35% du score GEO basé sur le contenu

        result.geo_score = min(score, 100)

    def _analyze_mobile(
        self, result: WebsiteAnalysisResult, soup: BeautifulSoup, html: str
    ):
        """Analyse de la compatibilité mobile."""
        # Viewport meta tag
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if viewport:
            result.has_viewport_meta = True

        # Indicateurs de responsive design
        responsive_indicators = [
            "@media",
            "max-width",
            "min-width",
            "responsive",
            "mobile",
            "bootstrap",
            "tailwind",
            "flex",
            "grid",
        ]

        html_lower = html.lower()
        responsive_count = sum(
            1 for indicator in responsive_indicators if indicator in html_lower
        )

        # Le site est considéré mobile-friendly si :
        # - Il a le viewport meta ET
        # - Il a au moins 2 indicateurs de responsive design
        result.is_mobile_friendly = result.has_viewport_meta and responsive_count >= 2

    def _analyze_quality(
        self, result: WebsiteAnalysisResult, soup: BeautifulSoup, html: str
    ):
        """
        Calcule le score de qualité global du site (0-100).

        Un score bas = site ancien/amateur = prospect prioritaire pour Kawanah Tourisme
        Un score haut = site moderne/pro = moins prioritaire

        Approche : on part de 50 (neutre) et on ajuste avec des bonus/malus.
        Les malus d'obsolescence sont forts car un site qui « a l'air vieux » est
        le signal #1 pour la prospection Kawanah.
        """
        score = 50  # Score de base neutre
        html_lower = html.lower()

        # === 1. STRUCTURE HTML5 SÉMANTIQUE (critère majeur) ===
        # Un site sans balises sémantiques HTML5 est structurellement daté.
        html5_tags = [
            "<header",
            "<footer",
            "<nav",
            "<main",
            "<article",
            "<section",
            "<aside",
        ]
        html5_count = sum(1 for tag in html5_tags if tag in html_lower)

        if html5_count >= 5:
            score += 15  # Excellent — structure moderne complète
        elif html5_count >= 3:
            score += 8
        elif html5_count == 0:
            score -= 15  # AUCUNE balise sémantique → site clairement ancien

        # === 2. INDICATEURS D'OBSOLESCENCE (chaque occurrence pèse lourd) ===
        old_count = sum(
            1 for indicator in self.OLD_SITE_INDICATORS if indicator in html_lower
        )

        # Indicateurs supplémentaires d'obsolescence
        extra_old_indicators = [
            "<center>",  # Balise dépréciée depuis HTML4
            'align="center"',  # Attribut alignement inline (pré-CSS)
            "cellpadding",  # Layout par tableaux
            "cellspacing",
            "valign=",  # Vertical align dans les tables
            "hspace=",  # Espacement images inline
            "vspace=",
            "<!--[if",  # Commentaires conditionnels IE
            "text-decoration:blink",
        ]
        old_count += sum(1 for ind in extra_old_indicators if ind in html_lower)

        # Chaque indicateur d'obsolescence coûte cher
        if old_count >= 4:
            score -= 25  # Site très ancien, multiples signaux
        elif old_count >= 2:
            score -= 15
        elif old_count >= 1:
            score -= 12

        # === 3. INDICATEURS DE MODERNITÉ ===
        modern_count = sum(
            1 for indicator in self.MODERN_INDICATORS if indicator in html_lower
        )

        # Bonus modéré — la modernité technique ne compense pas un design obsolète
        if modern_count >= 4 and old_count == 0:
            score += 15
        elif modern_count >= 2 and old_count == 0:
            score += 8
        elif modern_count >= 1 and old_count == 0:
            score += 3

        # === 4. HTTPS ===
        if result.uses_https:
            score += 5  # Réduit de 10 à 5 — HTTPS seul ne rend pas un site moderne
        else:
            score -= 15

        # === 5. TEMPS DE CHARGEMENT ===
        if result.load_time_ms is not None:
            if result.load_time_ms < 1000:
                score += 5
            elif result.load_time_ms > 6000:
                score -= 15
            elif result.load_time_ms > 4000:
                score -= 5

        # === 6. IMAGES MODERNES ===
        if ".webp" in html_lower or ".avif" in html_lower:
            score += 5
        if 'loading="lazy"' in html_lower or "lazyload" in html_lower:
            score += 5

        # Que des vieilles images (.gif animé, .bmp) → malus
        imgs = soup.find_all("img")
        if imgs:
            old_img_exts = [".gif", ".bmp"]
            old_img_count = sum(
                1
                for img in imgs
                if any(
                    ext in (img.get("src", "") or "").lower() for ext in old_img_exts
                )
            )
            if old_img_count > len(imgs) * 0.5:
                score -= 8

        # === 7. CSS/DESIGN MODERNE ===
        has_grid = "display:grid" in html_lower or "display: grid" in html_lower
        has_css_vars = "--" in html_lower and "var(" in html_lower

        if has_grid:
            score += 5
        if has_css_vars:
            score += 5
        # Flexbox seul n'est plus un indicateur fort (même Bootstrap 3 l'utilise)

        # === 8. MOBILE-FRIENDLY ===
        if result.is_mobile_friendly:
            score += 5  # Réduit — viewport + bootstrap ne veut pas dire bon mobile
        else:
            score -= 12

        # === 9. SEO (indicateur d'entretien du site) ===
        if result.seo_score >= 70:
            score += 5
        elif result.seo_score < 30:
            score -= 8

        # === 10. CMS / BUILDERS ===
        # CMS modernes
        modern_cms = [
            "wordpress",
            "wix",
            "squarespace",
            "webflow",
            "shopify",
            "astro",
            "next",
            "nuxt",
            "gatsby",
        ]
        if any(cms in html_lower for cms in modern_cms):
            score += 5

        # Vieux builders → malus fort (FrontPage, Dreamweaver = années 2000)
        # Note : "frontpage" est aussi dans OLD_SITE_INDICATORS, mais le malus builder
        # est intentionnel en plus — un site FrontPage est un signal fort d'obsolescence
        old_builders = ["frontpage", "dreamweaver", "golive", "nvu", "iweb", "homesite"]
        old_builder_count = sum(1 for builder in old_builders if builder in html_lower)
        if old_builder_count:
            score -= 15

        # === 11. DESIGN PATTERNS MODERNES vs DATÉS ===
        # Hero section / bannière moderne
        hero_indicators = [
            "hero",
            "banner",
            "jumbotron",
            "slider",
            "carousel",
            "swiper",
        ]
        has_hero = any(ind in html_lower for ind in hero_indicators)

        # Footer riche (liens, réseaux sociaux, copyright récent)
        import re

        copyright_years = re.findall(r"(?:©|copyright)\s*(\d{4})", html_lower)
        recent_copyright = (
            any(int(y) >= 2022 for y in copyright_years) if copyright_years else False
        )

        if not has_hero and html5_count == 0:
            score -= 8  # Pas de hero + pas de HTML5 sémantique = site daté

        if copyright_years and not recent_copyright:
            oldest = min(int(y) for y in copyright_years)
            if oldest < 2018:
                score -= 10  # Copyright ancien → site non maintenu

        # === FINALISATION ===
        result.quality_score = max(0, min(100, score))

    # Moteurs de réservation hôtelière courants (signal de réservation directe)
    BOOKING_ENGINES = [
        "amenitiz",
        "reservit",
        "thais",
        "d-edge",
        "availpro",
        "cubilis",
        "secutix",
        "guestonline",
        "zenchef",
        "elloha",
        "booking-engine",
        "synxis",
        "mews",
        "bookassist",
        "vega",
        "open-pro",
        "anytime",
        "lodgify",
    ]

    def _analyze_features(
        self, result: WebsiteAnalysisResult, soup: BeautifulSoup, html: str
    ):
        """
        Détecte les fonctionnalités concrètes du site et construit la liste
        des constats d'audit utilisés comme arguments commerciaux.
        """
        html_lower = html.lower()

        # --- Formulaire de contact ---
        forms = soup.find_all("form")
        has_textarea = bool(soup.find("textarea"))
        has_email_input = bool(soup.find("input", attrs={"type": "email"}))
        contact_keywords = any(
            kw in html_lower for kw in ["nous contacter", "formulaire de contact"]
        )
        result.has_contact_form = bool(
            (forms and (has_textarea or has_email_input)) or contact_keywords
        )

        # --- Réservation en direct (moteur ou formulaire de réservation) ---
        detected_engines = [eng for eng in self.BOOKING_ENGINES if eng in html_lower]
        engine = bool(detected_engines)
        reservation_keywords = any(
            kw in html_lower
            for kw in [
                "réserver",
                "reserver",
                "réservation en ligne",
                "reservation en ligne",
                "vérifier les disponibilités",
                "verifier les disponibilites",
                "book now",
                "check availability",
            ]
        )
        form_action_resa = any(
            "reserv" in (f.get("action", "") or "").lower()
            or "booking" in (f.get("action", "") or "").lower()
            for f in forms
        )
        result.has_reservation = bool(
            engine or form_action_resa or reservation_keywords
        )
        result.has_booking_system = result.has_reservation
        result.booking_platforms = detected_engines

        # --- Avis clients affichés sur le site ---
        result.has_embedded_reviews = any(
            kw in html_lower
            for kw in [
                "tripadvisor",
                "elfsight",
                "trustindex",
                "aggregaterating",
                "avis clients",
                "avis google",
                "google reviews",
                "témoignages",
                "temoignages",
            ]
        )

        # --- Carte d'accès / localisation ---
        map_in_iframe = any(
            "google.com/maps" in (i.get("src", "") or "").lower()
            or "maps.google" in (i.get("src", "") or "").lower()
            or "openstreetmap" in (i.get("src", "") or "").lower()
            for i in soup.find_all("iframe")
        )
        result.has_map = bool(
            map_in_iframe
            or any(
                kw in html_lower
                for kw in ["leaflet", "mapbox", "gmp-map", "maps.googleapis"]
            )
        )

        # --- Galerie photos ---
        img_count = len(soup.find_all("img"))
        result.has_photo_gallery = bool(
            img_count >= 8
            or any(
                kw in html_lower
                for kw in [
                    "galerie",
                    "gallery",
                    "lightbox",
                    "fancybox",
                    "swiper",
                    "slick",
                ]
            )
        )

        # --- Design daté (score qualité bas) ---
        result.design_dated = result.quality_score < 45

        # --- Construction des constats concrets (ordre = priorité argumentaire) ---
        findings: list[str] = []
        if not result.is_mobile_friendly:
            findings.append("le site n'est pas adapté au mobile (pas responsive)")
        if result.design_dated:
            findings.append("le design est daté et manque de modernité")
        if not result.has_reservation:
            findings.append("aucune réservation en direct sur le site")
        if not result.has_contact_form:
            findings.append("pas de formulaire de contact")
        if not result.has_embedded_reviews:
            findings.append("les avis clients ne sont pas affichés sur le site")
        if not result.has_map:
            findings.append("pas de carte d'accès ni de plan de localisation")
        if not result.has_photo_gallery:
            findings.append("peu de mise en valeur photo du lieu")
        result.audit_findings = findings


def build_website_audit(analysis: WebsiteAnalysisResult) -> dict:
    """Construit le dict d'audit concret stocké sur le lead (lead.website_audit)."""
    return {
        "is_mobile_friendly": analysis.is_mobile_friendly,
        "has_contact_form": analysis.has_contact_form,
        "has_reservation": analysis.has_reservation,
        "has_embedded_reviews": analysis.has_embedded_reviews,
        "has_map": analysis.has_map,
        "has_photo_gallery": analysis.has_photo_gallery,
        "design_dated": analysis.design_dated,
        "findings": analysis.audit_findings,
    }


class ScoringService:
    """Service principal de scoring des leads."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.analyzer = WebsiteAnalyzer()

    async def close(self):
        """Ferme les ressources."""
        await self.analyzer.close()

    async def analyze_and_score_lead(self, lead: Lead, force: bool = False) -> dict:
        """
        Analyse le site web d'un lead et met à jour son score.
        Saute l'analyse si le lead a été mis à jour dans les 7 derniers jours (sauf si force=True).

        Returns:
            dict avec les résultats de l'analyse
        """
        from datetime import timedelta

        # Cache : ne pas re-analyser si fait récemment (< 7 jours)
        if (
            not force
            and lead.website_quality_score is not None
            and lead.updated_at
            and (datetime.utcnow() - lead.updated_at) < timedelta(days=7)
        ):
            logger.info(f"Scoring de {lead.name} déjà à jour (< 7 jours), skip analyse")
            return {
                "lead_id": lead.id,
                "lead_name": lead.name,
                "website": lead.website,
                "cached": True,
                "final_score": lead.score,
                "priority": lead.priority_level,
            }

        logger.info(f"Analyse du lead: {lead.name} (ID: {lead.id})")

        analysis_result = None

        # Analyser le site web si URL disponible
        if lead.website:
            if lead.website_match_status != WebsiteMatchStatus.VERIFIED:
                match = apply_website_match(
                    lead,
                    lead.website,
                    source=lead.website_match_source or lead.source or "existing",
                )
                if match.status != WebsiteMatchStatus.VERIFIED:
                    lead.has_website = None
                    lead.website_quality_score = None
                    lead.website_audit = None
                    lead.score = lead.calculate_score()
                    await self.db.commit()
                    logger.warning(
                        f"Analyse bloquée pour {lead.name}: site non validé "
                        f"({match.status.value}, confiance={match.confidence})"
                    )
                    return {
                        "lead_id": lead.id,
                        "lead_name": lead.name,
                        "website": lead.website,
                        "website_match_status": match.status.value,
                        "website_match_confidence": match.confidence,
                        "blocked": True,
                        "reason": "site_matching_not_verified",
                        "final_score": lead.score,
                    }

            analysis_result = await self.analyzer.analyze(lead.website)

            if analysis_result.success:
                lead.website_quality_score = analysis_result.quality_score
                lead.seo_score = analysis_result.seo_score
                lead.geo_score = analysis_result.geo_score
                lead.is_mobile_friendly = analysis_result.is_mobile_friendly
                lead.has_booking_system = analysis_result.has_reservation
                lead.website_audit = build_website_audit(analysis_result)
                lead.has_website = True
            else:
                # Site inaccessible (erreur 5xx, timeout, etc.)
                # On garde has_website=True car l'URL existe — le site est juste down
                lead.has_website = True
                logger.warning(
                    f"Site inaccessible mais URL connue: {lead.website} — {analysis_result.error}"
                )
        elif lead.has_website is None:
            # Pas d'URL ET pas encore vérifié → recherche active
            from app.services.web_verification_service import WebVerificationService

            verifier = WebVerificationService()
            found = await verifier.search_website(
                lead.name,
                lead.city,
                str(lead.lead_type.value) if lead.lead_type else "établissement",
            )
            if found.found and found.url:
                lead.website = found.url
                lead.has_website = True
                logger.info(
                    f"Site trouvé via recherche: {found.url} (confiance: {found.confidence})"
                )
                # Analyser le site fraîchement trouvé
                analysis_result = await self.analyzer.analyze(found.url)
                if analysis_result.success:
                    lead.website_quality_score = analysis_result.quality_score
                    lead.seo_score = analysis_result.seo_score
                    lead.geo_score = analysis_result.geo_score
                    lead.is_mobile_friendly = analysis_result.is_mobile_friendly
                    lead.has_booking_system = analysis_result.has_reservation
                    lead.website_audit = build_website_audit(analysis_result)
            else:
                lead.has_website = False
                logger.info(
                    f"Aucun site trouvé pour {lead.name} après recherche active"
                )

        # Analyse DataForSEO (si credentials configurés)
        dataforseo_metrics = None
        if lead.website and settings.dataforseo_login and settings.dataforseo_password:
            try:
                from app.services.dataforseo_service import DataForSEOClient

                client = DataForSEOClient(
                    login=settings.dataforseo_login,
                    password=settings.dataforseo_password,
                )
                dataforseo_metrics = await client.get_domain_metrics(lead.website)
                await client.close()

                if dataforseo_metrics.success:
                    lead.dataforseo_domain_rank = dataforseo_metrics.domain_rank
                    lead.dataforseo_organic_keywords = (
                        dataforseo_metrics.organic_keywords
                    )
                    lead.dataforseo_organic_traffic = dataforseo_metrics.organic_traffic
                    lead.dataforseo_analyzed_at = datetime.utcnow()
            except Exception as e:
                logger.warning(f"DataForSEO non disponible pour {lead.name}: {e}")

        # Recalculer le score global
        lead.update_score()

        await self.db.commit()

        return {
            "lead_id": lead.id,
            "lead_name": lead.name,
            "website": lead.website,
            "analysis": {
                "success": analysis_result.success if analysis_result else False,
                "quality_score": analysis_result.quality_score
                if analysis_result
                else None,
                "seo_score": analysis_result.seo_score if analysis_result else None,
                "geo_score": analysis_result.geo_score if analysis_result else None,
                "geo_details": {
                    "has_structured_data": analysis_result.has_structured_data,
                    "has_faq_schema": analysis_result.has_faq_schema,
                    "has_local_business": analysis_result.has_local_business,
                    "has_clear_contact": analysis_result.has_clear_contact,
                    "content_richness": analysis_result.content_richness,
                }
                if analysis_result
                else None,
                "is_mobile_friendly": analysis_result.is_mobile_friendly
                if analysis_result
                else None,
                "load_time_ms": analysis_result.load_time_ms
                if analysis_result
                else None,
                "error": analysis_result.error if analysis_result else None,
            }
            if analysis_result
            else None,
            "dataforseo": {
                "domain_rank": dataforseo_metrics.domain_rank,
                "organic_keywords": dataforseo_metrics.organic_keywords,
                "organic_traffic": dataforseo_metrics.organic_traffic,
                "seo_presence": dataforseo_metrics.seo_presence,
                "opportunity_score": dataforseo_metrics.opportunity_score,
            }
            if dataforseo_metrics and dataforseo_metrics.success
            else None,
            "final_score": lead.score,
            "priority": lead.priority_level,
        }

    async def analyze_leads_batch(
        self,
        lead_ids: Optional[list[int]] = None,
        limit: int = 10,
        only_unanalyzed: bool = True,
    ) -> dict:
        """
        Analyse plusieurs leads en batch.

        Args:
            lead_ids: Liste d'IDs spécifiques à analyser
            limit: Nombre max de leads à analyser
            only_unanalyzed: Si True, n'analyse que les leads sans score de qualité
        """
        query = select(Lead).where(Lead.website.isnot(None))

        if lead_ids:
            query = query.where(Lead.id.in_(lead_ids))
        elif only_unanalyzed:
            query = query.where(Lead.website_quality_score.is_(None))

        query = query.limit(limit)

        result = await self.db.execute(query)
        leads = result.scalars().all()

        logger.info(f"Analyse de {len(leads)} leads...")

        results = []
        for lead in leads:
            try:
                analysis_result = await self.analyze_and_score_lead(lead)
                results.append(analysis_result)
                # Pause pour éviter le rate limiting
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Erreur analyse lead {lead.id}: {e}")
                results.append(
                    {"lead_id": lead.id, "lead_name": lead.name, "error": str(e)}
                )

        await self.close()

        return {
            "total_analyzed": len(results),
            "results": results,
        }

    async def get_leads_by_priority(
        self,
        segment: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        Récupère les leads triés par score de priorité.

        Args:
            segment: Filtrer par segment ("hot", "warm", "cold")
            limit: Nombre de résultats
            offset: Offset pour la pagination
        """
        query = select(Lead).order_by(Lead.score.desc())

        if segment:
            if segment == "hot":
                query = query.where(Lead.score >= 80)
            elif segment == "warm":
                query = query.where(Lead.score >= 50, Lead.score < 80)
            elif segment == "cold":
                query = query.where(Lead.score < 50)

        # Compter le total
        count_query = select(func.count(Lead.id))
        if segment:
            if segment == "hot":
                count_query = count_query.where(Lead.score >= 80)
            elif segment == "warm":
                count_query = count_query.where(Lead.score >= 50, Lead.score < 80)
            elif segment == "cold":
                count_query = count_query.where(Lead.score < 50)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Récupérer les leads
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        leads = result.scalars().all()

        return {
            "total": total,
            "segment": segment,
            "leads": [
                {
                    "id": lead.id,
                    "name": lead.name,
                    "city": lead.city,
                    "website": lead.website,
                    "score": lead.score,
                    "priority": lead.priority_level,
                    "status": lead.status.value,
                    "has_website": lead.has_website,
                    "website_quality_score": lead.website_quality_score,
                    "seo_score": lead.seo_score,
                    "geo_score": lead.geo_score,
                    "is_mobile_friendly": lead.is_mobile_friendly,
                }
                for lead in leads
            ],
        }

    async def get_scoring_stats(self) -> dict:
        """Retourne des statistiques sur le scoring des leads."""
        # Total leads
        total_result = await self.db.execute(select(func.count(Lead.id)))
        total = total_result.scalar()

        # Par segment
        hot_result = await self.db.execute(
            select(func.count(Lead.id)).where(Lead.score >= 80)
        )
        hot_count = hot_result.scalar()

        warm_result = await self.db.execute(
            select(func.count(Lead.id)).where(Lead.score >= 50, Lead.score < 80)
        )
        warm_count = warm_result.scalar()

        cold_result = await self.db.execute(
            select(func.count(Lead.id)).where(Lead.score < 50)
        )
        cold_count = cold_result.scalar()

        # Analysés vs non analysés
        analyzed_result = await self.db.execute(
            select(func.count(Lead.id)).where(Lead.website_quality_score.isnot(None))
        )
        analyzed_count = analyzed_result.scalar()

        # Moyenne des scores
        avg_result = await self.db.execute(select(func.avg(Lead.score)))
        avg_score = avg_result.scalar() or 0

        return {
            "total_leads": total,
            "segments": {
                "hot": {"count": hot_count, "label": "🔥 CHAUD (score >= 80)"},
                "warm": {"count": warm_count, "label": "😐 TIÈDE (50-79)"},
                "cold": {"count": cold_count, "label": "❄️ FROID (< 50)"},
            },
            "analysis": {
                "analyzed": analyzed_count,
                "pending": total - analyzed_count,
            },
            "average_score": round(avg_score, 1),
        }


# Fonctions helpers pour l'API
async def analyze_lead_by_id(db: AsyncSession, lead_id: int) -> dict:
    """Analyse un lead par son ID."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        return {"error": "Lead non trouvé"}

    service = ScoringService(db)
    try:
        return await service.analyze_and_score_lead(lead)
    finally:
        await service.close()
