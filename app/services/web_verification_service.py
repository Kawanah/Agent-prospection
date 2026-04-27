"""
Service de vérification web - Recherche si un établissement a un site web.

Stratégie multi-couches (du plus fiable au moins fiable) :
1. Vérification directe d'URL candidates générées à partir du nom
2. Recherche DuckDuckGo avec plusieurs variantes de requête
3. Fallback : premier résultat non-annuaire

Le but : NE JAMAIS dire "pas de site" à quelqu'un qui en a un.
"""

import re
import unicodedata
import httpx
from typing import Optional, List
from dataclasses import dataclass
from urllib.parse import quote_plus

from loguru import logger


# ─── Mots vides à ignorer dans le matching ────────────────────────────────────
_STOP_WORDS = frozenset(
    {
        "le",
        "la",
        "les",
        "de",
        "du",
        "des",
        "un",
        "une",
        "au",
        "aux",
        "en",
        "et",
        "ou",
        "sur",
        "par",
        "pour",
        "avec",
        "dans",
        "son",
        "sa",
        "ses",
        "ce",
        "cette",
        "ces",
        "qui",
        "que",
        "est",
        "the",
        "and",
        "of",
        "in",
        "at",
        "to",
        "for",
        "hotel",
        "hôtel",
        "camping",
        "gite",
        "gîte",
        "residence",
        "résidence",
        "chambre",
        "hotes",
        "hôtes",
        "auberge",
        "village",
        "vacances",
        "tourisme",
        "loisirs",
        "centre",
        "parc",
    }
)

# ─── Domaines annuaires/plateformes à exclure ────────────────────────────────
_EXCLUDED_DOMAINS = frozenset(
    {
        "booking.com",
        "tripadvisor",
        "hotels.com",
        "expedia",
        "pagesjaunes",
        "google.com",
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "linkedin.com",
        "x.com",
        "yelp",
        "airbnb",
        "abritel",
        "gites-de-france.com",
        "camping-and-co",
        "campings.com",
        "yelloh",
        "tohapi",
        "wikipedia",
        "annuaire",
        "118",
        "horaires",
        "cylex",
        "starofservice",
        "mappy",
        "kompass",
        "societe.com",
        "verif.com",
        "infogreffe",
        "pappers",
        "youtube.com",
        "tiktok.com",
        "pinterest.com",
        "trivago",
        "kayak",
        "linternaute",
        "routard.com",
        "petitfute",
        "michelin.com",
        "viamichelin",
        "leboncoin",
        "groupon",
    }
)


def _strip_accents(s: str) -> str:
    """Supprime les accents d'une chaîne."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _slugify(s: str) -> str:
    """Convertit une chaîne en slug pour deviner un nom de domaine."""
    s = _strip_accents(s.lower())
    s = re.sub(r"[''`]", "", s)  # Apostrophes
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def _significant_words(name: str) -> set[str]:
    """Extrait les mots significatifs d'un nom d'établissement (sans stop words)."""
    words = set()
    for w in _strip_accents(name).lower().split():
        clean = re.sub(r"[^a-z0-9]", "", w)
        if (
            len(clean) >= 3
            and clean not in _STOP_WORDS
            and _strip_accents(clean) not in _STOP_WORDS
        ):
            words.add(clean)
    return words


def _is_excluded(url: str) -> bool:
    """Vérifie si une URL appartient à un domaine exclu."""
    url_lower = url.lower()
    return any(excl in url_lower for excl in _EXCLUDED_DOMAINS)


@dataclass
class WebSearchResult:
    """Résultat d'une recherche web."""

    found: bool
    url: Optional[str] = None
    title: Optional[str] = None
    source: str = "unknown"
    confidence: str = "low"  # low, medium, high


class WebVerificationService:
    """
    Service robuste pour vérifier si un établissement a un site web.

    Stratégie en 3 couches :
    1. Deviner des URLs à partir du nom et les tester directement
    2. Rechercher via DuckDuckGo (HTML) avec plusieurs variantes
    3. Accepter le premier résultat non-annuaire si rien ne matche par nom
    """

    def __init__(self):
        self.timeout = 10.0
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        }

    # ─── Point d'entrée principal ─────────────────────────────────────────────

    async def search_website(
        self,
        establishment_name: str,
        city: Optional[str] = None,
        establishment_type: str = "établissement",
    ) -> WebSearchResult:
        """
        Recherche le site web d'un établissement avec une stratégie multi-couches.
        """
        logger.info(f"🔍 Recherche web: {establishment_name} ({city or '?'})")

        # ── Couche 1 : Deviner et tester des URLs directement ──
        result = await self._try_direct_urls(establishment_name, city)
        if result.found:
            return result

        # ── Couche 2 : Recherche DuckDuckGo (plusieurs variantes) ──
        queries = self._build_search_queries(
            establishment_name, city, establishment_type
        )
        all_search_results = []

        for query in queries:
            ddg_results = await self._fetch_duckduckgo(query)
            if ddg_results:
                all_search_results.extend(ddg_results)

                # Tenter un matching strict
                result = self._find_official_site(ddg_results, establishment_name)
                if result.found:
                    return result

        # ── Couche 3 : Fallback — premier site non-annuaire ──
        if all_search_results:
            return self._first_non_directory(all_search_results)

        return WebSearchResult(found=False, source="exhausted")

    # ─── Couche 1 : URLs devinées ────────────────────────────────────────────

    async def _try_direct_urls(
        self, name: str, city: Optional[str] = None
    ) -> WebSearchResult:
        """Génère des noms de domaine probables et vérifie leur existence."""
        slug = _slugify(name)
        # Variantes avec/sans tirets
        compact = slug.replace("-", "")

        candidates = []
        for domain in [slug, compact]:
            if len(domain) < 4:
                continue
            candidates.append(f"https://www.{domain}.fr")
            candidates.append(f"https://{domain}.fr")
            candidates.append(f"https://www.{domain}.com")

        # Variante "type-nom-ville" courante dans l'hospitalité
        if city:
            city_slug = _slugify(city)
            candidates.append(f"https://www.{slug}-{city_slug}.fr")

        for url in candidates:
            if await self._url_is_live(url):
                logger.info(f"✅ URL devinée accessible: {url}")
                return WebSearchResult(
                    found=True,
                    url=url,
                    title=None,
                    source="direct_guess",
                    confidence="medium",
                )

        return WebSearchResult(found=False)

    async def _url_is_live(self, url: str) -> bool:
        """Vérifie rapidement si une URL répond (HEAD puis GET fallback)."""
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                resp = await client.head(url, headers=self.headers)
                if resp.status_code == 405:
                    resp = await client.get(url, headers=self.headers)
                return resp.status_code < 500
        except Exception:
            # Tenter HTTP si HTTPS échoue
            if url.startswith("https://"):
                try:
                    http_url = "http://" + url[8:]
                    async with httpx.AsyncClient(
                        timeout=6.0, follow_redirects=True
                    ) as client:
                        resp = await client.get(http_url, headers=self.headers)
                        return resp.status_code < 500
                except Exception:
                    pass
        return False

    # ─── Couche 2 : Recherche DuckDuckGo ─────────────────────────────────────

    def _build_search_queries(
        self, name: str, city: Optional[str], est_type: str
    ) -> list[str]:
        """Construit plusieurs variantes de requêtes pour maximiser les chances."""
        queries = []

        # Variante 1 : nom + ville (le plus simple et efficace)
        if city:
            queries.append(f'"{name}" {city}')
        else:
            queries.append(f'"{name}"')

        # Variante 2 : nom + ville + "site officiel"
        parts = [name]
        if city:
            parts.append(city)
        parts.append("site officiel")
        queries.append(" ".join(parts))

        # Variante 3 : nom + type + ville (sans guillemets)
        parts3 = [name, est_type]
        if city:
            parts3.append(city)
        queries.append(" ".join(parts3))

        return queries

    async def _fetch_duckduckgo(self, query: str) -> List[dict]:
        """Fait une recherche DuckDuckGo HTML et extrait les résultats."""
        try:
            encoded = quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers)

                if response.status_code != 200:
                    return []

                return self._parse_duckduckgo_html(response.text)

        except Exception as e:
            logger.warning(f"Erreur DuckDuckGo pour '{query}': {e}")
            return []

    def _parse_duckduckgo_html(self, html: str) -> List[dict]:
        """Parse les résultats DuckDuckGo (compatible 2024-2025+)."""
        results = []

        # Pattern 1 : ancienne structure (class="result__a")
        pattern_old = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        # Pattern 2 : nouvelle structure (data-testid="result-title-a")
        pattern_new = (
            r'<a[^>]*data-testid="result-title-a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        )
        # Pattern 3 : liens génériques dans les résultats
        pattern_generic = (
            r'<a[^>]*class="[^"]*result[^"]*"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        )

        for pattern in [pattern_old, pattern_new, pattern_generic]:
            matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
            for raw_url, raw_title in matches[:15]:
                clean_url = self._extract_real_url(raw_url)
                if clean_url and clean_url.startswith("http"):
                    # Nettoyer le titre (enlever les balises HTML internes)
                    title = re.sub(r"<[^>]+>", "", raw_title).strip()
                    results.append({"url": clean_url, "title": title})

        # Dédupliquer par domaine
        seen_domains = set()
        unique = []
        for r in results:
            domain = re.sub(r"https?://(www\.)?", "", r["url"]).split("/")[0]
            if domain not in seen_domains:
                seen_domains.add(domain)
                unique.append(r)

        return unique[:10]

    def _extract_real_url(self, duckduckgo_url: str) -> Optional[str]:
        """Extrait l'URL réelle depuis l'URL DuckDuckGo encodée."""
        if "uddg=" in duckduckgo_url:
            match = re.search(r"uddg=([^&]+)", duckduckgo_url)
            if match:
                from urllib.parse import unquote

                return unquote(match.group(1))

        if duckduckgo_url.startswith("http"):
            return duckduckgo_url

        return None

    # ─── Matching : trouver le site officiel ─────────────────────────────────

    def _find_official_site(
        self, results: List[dict], establishment_name: str
    ) -> WebSearchResult:
        """
        Cherche le site officiel dans les résultats de recherche.
        Exclut les annuaires et vérifie le matching par mots significatifs.
        """
        name_words = _significant_words(establishment_name)
        if not name_words:
            # Nom trop court/générique → on ne peut pas matcher
            return WebSearchResult(found=False, source="duckduckgo")

        for result in results:
            url = result.get("url", "")
            if _is_excluded(url):
                continue

            title = _strip_accents(result.get("title", "").lower())
            url_slug = _strip_accents(url.lower())

            # Mots du nom trouvés dans le titre ou l'URL
            in_title = {w for w in name_words if w in title}
            in_url = {w for w in name_words if w in url_slug}
            matched = in_title | in_url

            if not matched:
                continue

            # Score de correspondance : pondérer par longueur de mot et nombre
            score = sum(len(w) for w in matched)
            coverage = len(matched) / len(name_words) if name_words else 0

            # Seuils : au moins un mot long (≥5) ou 2 mots quelconques, ou 50%+ de couverture
            long_words = [w for w in matched if len(w) >= 5]
            if long_words or len(matched) >= 2 or coverage >= 0.5:
                confidence = (
                    "high" if coverage >= 0.5 or len(matched) >= 2 else "medium"
                )
                logger.info(
                    f"✅ Site trouvé: {url} "
                    f"(confiance: {confidence}, mots: {matched}, couverture: {coverage:.0%})"
                )
                return WebSearchResult(
                    found=True,
                    url=url,
                    title=result.get("title"),
                    source="duckduckgo",
                    confidence=confidence,
                )

        return WebSearchResult(found=False, source="duckduckgo")

    # ─── Couche 3 : Fallback — premier résultat non-annuaire ─────────────────

    def _first_non_directory(self, results: List[dict]) -> WebSearchResult:
        """
        Dernier recours : prend le premier résultat qui n'est pas un annuaire.
        Confiance basse — mais mieux que de dire "pas de site" à tort.
        """
        for result in results:
            url = result.get("url", "")
            if not _is_excluded(url):
                logger.info(f"⚠️ Fallback (premier non-annuaire): {url}")
                return WebSearchResult(
                    found=True,
                    url=url,
                    title=result.get("title"),
                    source="duckduckgo_fallback",
                    confidence="low",
                )

        return WebSearchResult(found=False, source="exhausted")

    # ─── Vérification d'URL existante ────────────────────────────────────────

    async def verify_url_accessible(self, url: str) -> bool:
        """Vérifie si une URL est accessible (HEAD → GET fallback → HTTP fallback)."""
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.head(url, headers=self.headers)
                if response.status_code == 405:
                    response = await client.get(url, headers=self.headers)
                return response.status_code < 500
        except Exception:
            # Tenter HTTP si HTTPS échoue
            if url.startswith("https://"):
                try:
                    http_url = "http://" + url[8:]
                    async with httpx.AsyncClient(
                        timeout=8.0, follow_redirects=True
                    ) as client:
                        response = await client.get(http_url, headers=self.headers)
                        return response.status_code < 500
                except Exception:
                    pass
            return False


async def verify_establishment_website(
    name: str,
    city: Optional[str] = None,
    current_url: Optional[str] = None,
) -> dict:
    """
    Vérifie si un établissement a un site web.
    Helper function pour l'API et l'agent.
    """
    service = WebVerificationService()

    result = {
        "establishment": name,
        "city": city,
        "has_website": False,
        "found_url": None,
        "current_url_valid": False,
        "confidence": "low",
        "recommendation": "",
    }

    # Vérifier l'URL actuelle si elle existe
    if current_url and current_url not in ["-", "n/a", "", None]:
        is_valid = await service.verify_url_accessible(current_url)
        result["current_url_valid"] = is_valid
        if is_valid:
            result["has_website"] = True
            result["found_url"] = current_url
            result["confidence"] = "high"
            result[
                "recommendation"
            ] = "URL actuelle valide — pas de création de site à proposer"
            return result

    # Rechercher activement
    search_result = await service.search_website(name, city)

    if search_result.found:
        result["has_website"] = True
        result["found_url"] = search_result.url
        result["confidence"] = search_result.confidence
        result["recommendation"] = (
            f"Site trouvé ({search_result.confidence}): {search_result.url} "
            f"— vérifier avant de prospecter"
        )
    else:
        result[
            "recommendation"
        ] = "Aucun site trouvé — bon candidat pour création de site"

    return result
