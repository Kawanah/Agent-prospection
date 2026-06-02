"""
Service d'enrichissement des leads.
Trouve automatiquement les informations manquantes :
- Informations établissement (téléphone, email, réseaux sociaux)
- Décideurs/contacts (nom, fonction, email)

Sources GRATUITES :
- Site web de l'établissement
- Google Search
- Societe.com (dirigeants)
- PagesJaunes
- Génération de patterns d'email

Sources PAYANTES (optionnelles) :
- Hunter.io
- Dropcontact
"""

import re
import asyncio
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.lead import Lead, LeadStatus
from app.models.contact import Contact, ContactRole
from app.services.http_safety import MAX_REDIRECTS, validate_public_http_url
from app.services.scoring_service import WebsiteAnalyzer
from app.services.web_verification_service import WebVerificationService

settings = get_settings()


@dataclass
class EnrichmentResult:
    """Résultat d'un enrichissement."""

    success: bool = False
    source: str = ""
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    contacts: list = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ContactInfo:
    """Information sur un contact trouvé."""

    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    role: ContactRole = ContactRole.OTHER
    linkedin_url: Optional[str] = None
    source: str = ""
    confidence: int = 0


class WebScraper:
    """Scraper web pour extraire des informations."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
        )

    async def close(self):
        await self.client.aclose()

    async def fetch_page(self, url: str) -> Optional[str]:
        """Récupère le contenu HTML d'une page."""
        try:
            current_url = validate_public_http_url(url)
            for _ in range(MAX_REDIRECTS + 1):
                response = await self.client.get(current_url, follow_redirects=False)
                if response.is_redirect:
                    location = response.headers.get("Location")
                    if not location:
                        return None
                    current_url = validate_public_http_url(
                        urllib.parse.urljoin(current_url, location)
                    )
                    continue
                break
            else:
                return None

            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.debug(f"Erreur fetch {url}: {e}")
            return None

    def extract_emails(self, html: str) -> list[str]:
        """Extrait les emails d'un contenu HTML."""
        pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        emails = re.findall(pattern, html)
        valid_emails = []
        for email in emails:
            email = email.lower()
            # Exclure les faux positifs
            if not any(
                x in email
                for x in [
                    "example.com",
                    "domain.com",
                    "test.",
                    "wixpress",
                    "sentry.io",
                    "schema.org",
                    "w3.org",
                    ".png",
                    ".jpg",
                    ".gif",
                ]
            ):
                valid_emails.append(email)
        return list(set(valid_emails))

    def extract_phones(self, html: str) -> list[str]:
        """Extrait les numéros de téléphone français."""
        patterns = [
            r"(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}",
            r"(?:(?:\+|00)33|0)[1-9]\d{8}",
        ]
        phones = []
        for pattern in patterns:
            matches = re.findall(pattern, html)
            phones.extend(matches)

        normalized = []
        for phone in phones:
            digits = re.sub(r"[^\d]", "", phone)
            if digits.startswith("33"):
                digits = "0" + digits[2:]
            if len(digits) == 10 and digits.startswith("0"):
                formatted = f"{digits[0:2]} {digits[2:4]} {digits[4:6]} {digits[6:8]} {digits[8:10]}"
                normalized.append(formatted)

        return list(set(normalized))

    def extract_social_links(self, html: str, soup: BeautifulSoup) -> dict:
        """Extrait les liens réseaux sociaux."""
        social = {"facebook_url": None, "instagram_url": None, "linkedin_url": None}

        for link in soup.find_all("a", href=True):
            href = link["href"].lower()
            if "facebook.com" in href and not social["facebook_url"]:
                social["facebook_url"] = link["href"]
            elif "instagram.com" in href and not social["instagram_url"]:
                social["instagram_url"] = link["href"]
            elif "linkedin.com" in href and not social["linkedin_url"]:
                social["linkedin_url"] = link["href"]

        return social


class GoogleSearchScraper:
    """Recherche Google pour trouver emails et contacts (GRATUIT)."""

    def __init__(self, web_scraper: WebScraper):
        self.scraper = web_scraper

    async def search_email_contact(
        self, name: str, city: Optional[str] = None
    ) -> EnrichmentResult:
        """Recherche email et contact via Google."""
        result = EnrichmentResult(source="google_search")

        try:
            # Construire la requête Google
            query = f'"{name}"'
            if city:
                query += f" {city}"
            query += " email contact"

            encoded_query = urllib.parse.quote(query)
            # Utiliser un moteur de recherche qui ne bloque pas
            search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

            logger.info(f"Recherche: {query}")

            html = await self.scraper.fetch_page(search_url)
            if not html:
                result.error = "Recherche impossible"
                return result

            # Extraire emails des résultats
            emails = self.scraper.extract_emails(html)
            phones = self.scraper.extract_phones(html)

            if emails:
                # Filtrer pour garder les emails pertinents
                relevant_emails = [
                    e
                    for e in emails
                    if not any(x in e for x in ["duckduckgo", "google", "bing"])
                ]
                if relevant_emails:
                    result.email = relevant_emails[0]

            if phones:
                result.phone = phones[0]

            result.success = bool(result.email or result.phone)
            return result

        except Exception as e:
            logger.error(f"Erreur recherche Google: {e}")
            result.error = str(e)
            return result


class SocieteComScraper:
    """Scraper Societe.com pour trouver les dirigeants (GRATUIT)."""

    def __init__(self, web_scraper: WebScraper):
        self.scraper = web_scraper
        self.base_url = "https://www.societe.com"

    async def search_company(
        self, name: str, city: Optional[str] = None
    ) -> EnrichmentResult:
        """Recherche une entreprise et ses dirigeants sur Societe.com."""
        result = EnrichmentResult(source="societe.com")

        try:
            # Recherche sur Societe.com
            query = name.replace(" ", "+")
            if city:
                query += f"+{city.replace(' ', '+')}"

            search_url = f"{self.base_url}/cgi-bin/search?champs={query}"
            logger.info(f"Societe.com recherche: {search_url}")

            html = await self.scraper.fetch_page(search_url)
            if not html:
                result.error = "Impossible d'accéder à Societe.com"
                return result

            soup = BeautifulSoup(html, "lxml")

            # Chercher les noms de dirigeants
            # Les dirigeants sont souvent dans des balises spécifiques
            dirigeants_patterns = [
                r"(?:Dirigeant|Gérant|Président|Directeur|PDG|CEO)[:\s]+([A-ZÀ-Ü][a-zà-ü]+\s+[A-ZÀ-Ü][A-ZÀ-Üa-zà-ü]+)",
                r"([A-ZÀ-Ü][a-zà-ü]+\s+[A-ZÀ-Ü][A-ZÀ-Üa-zà-ü]+)(?:\s*[-,]\s*(?:Gérant|Président|Directeur))",
            ]

            for pattern in dirigeants_patterns:
                matches = re.findall(pattern, html)
                for match in matches[:3]:  # Limiter à 3 dirigeants
                    name_parts = match.strip().split()
                    if len(name_parts) >= 2:
                        contact = ContactInfo(
                            full_name=match.strip(),
                            first_name=name_parts[0],
                            last_name=" ".join(name_parts[1:]),
                            role=ContactRole.DIRECTOR,
                            source="societe.com",
                            confidence=60,
                        )
                        result.contacts.append(contact)

            result.success = len(result.contacts) > 0
            return result

        except Exception as e:
            logger.error(f"Erreur Societe.com: {e}")
            result.error = str(e)
            return result


class EmailPatternGenerator:
    """Génère des emails probables à partir du nom et du domaine (GRATUIT)."""

    # Patterns d'email courants en France
    PATTERNS = [
        "{first}.{last}",  # jean.dupont
        "{first}{last}",  # jeandupont
        "{f}{last}",  # jdupont
        "{first}",  # jean
        "{last}",  # dupont
        "{first}-{last}",  # jean-dupont
        "{last}.{first}",  # dupont.jean
        "contact",  # contact@domain
        "info",  # info@domain
        "direction",  # direction@domain
        "reservation",  # reservation@domain
        "booking",  # booking@domain
    ]

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalise un nom pour l'email (supprime accents, minuscules)."""
        import unicodedata

        # Supprimer les accents
        name = "".join(
            c
            for c in unicodedata.normalize("NFD", name)
            if unicodedata.category(c) != "Mn"
        )
        # Minuscules et supprimer caractères spéciaux
        name = re.sub(r"[^a-zA-Z]", "", name.lower())
        return name

    def generate_emails(
        self,
        domain: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> list[dict]:
        """Génère des emails probables."""
        emails = []

        # Nettoyer le domaine
        domain = (
            domain.replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .split("/")[0]
        )

        if first_name and last_name:
            first = self.normalize_name(first_name)
            last = self.normalize_name(last_name)
            f = first[0] if first else ""

            for pattern in self.PATTERNS[:7]:  # Patterns avec nom
                try:
                    email_local = pattern.format(first=first, last=last, f=f)
                    email = f"{email_local}@{domain}"
                    confidence = (
                        70 if pattern in ["{first}.{last}", "{f}{last}"] else 50
                    )
                    emails.append({"email": email, "confidence": confidence})
                except:
                    pass

        # Ajouter les emails génériques
        for pattern in self.PATTERNS[7:]:
            email = f"{pattern}@{domain}"
            emails.append({"email": email, "confidence": 40})

        return emails


class PagesJaunesScraper:
    """Scraper pour PagesJaunes.fr (GRATUIT)."""

    def __init__(self, web_scraper: WebScraper):
        self.scraper = web_scraper
        self.base_url = "https://www.pagesjaunes.fr"

    async def search(self, name: str, city: Optional[str] = None) -> EnrichmentResult:
        """Recherche un établissement sur PagesJaunes."""
        result = EnrichmentResult(source="pagesjaunes")

        try:
            query = name.replace(" ", "+")
            if city:
                query += f"+{city.replace(' ', '+')}"

            search_url = f"{self.base_url}/recherche/{query}"
            logger.info(f"PagesJaunes recherche: {search_url}")

            html = await self.scraper.fetch_page(search_url)
            if not html:
                result.error = "Impossible d'accéder à PagesJaunes"
                return result

            phones = self.scraper.extract_phones(html)
            if phones:
                result.phone = phones[0]

            emails = self.scraper.extract_emails(html)
            if emails:
                result.email = emails[0]

            result.success = bool(result.phone or result.email)
            return result

        except Exception as e:
            logger.error(f"Erreur PagesJaunes: {e}")
            result.error = str(e)
            return result


class WebsiteScraper:
    """Scraper pour le site web de l'établissement (GRATUIT)."""

    # Chemins classiques à vérifier
    CONTACT_PATHS = [
        "/contact",
        "/contacts",
        "/nous-contacter",
        "/contactez-nous",
        "/mentions-legales",
        "/mentions_legales",
        "/legal",
        "/a-propos",
        "/about",
        "/qui-sommes-nous",
        "/infos-pratiques",
        "/informations",
        "/info",
        "/reservation",
        "/reservations",
        "/booking",
        "/cgu",
        "/cgv",
        "/politique-de-confidentialite",
    ]

    # Mots-clés dans les liens internes qui mènent souvent à un email
    CONTACT_LINK_KEYWORDS = [
        "contact",
        "contacter",
        "email",
        "mail",
        "mention",
        "legal",
        "propos",
        "about",
        "info",
        "pratique",
        "acces",
        "accès",
        "reservation",
        "booking",
    ]

    def __init__(self, web_scraper: WebScraper):
        self.scraper = web_scraper

    def _extract_mailto(self, soup: BeautifulSoup) -> list[str]:
        """Extrait les emails des liens mailto: — méthode la plus fiable."""
        emails = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip().lower()
                if email and "@" in email:
                    emails.append(email)
        return list(set(emails))

    def _find_contact_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Trouve les liens internes qui mènent probablement à une page contact."""
        from urllib.parse import urljoin, urlparse

        base_domain = urlparse(base_url).netloc
        contact_urls = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            # Seulement les liens internes
            if parsed.netloc and parsed.netloc != base_domain:
                continue

            # Vérifier l'URL et le texte du lien
            href_lower = href.lower()
            text_lower = (link.get_text() or "").lower()

            if any(
                kw in href_lower or kw in text_lower
                for kw in self.CONTACT_LINK_KEYWORDS
            ):
                if full_url not in contact_urls:
                    contact_urls.append(full_url)

        return contact_urls[:8]  # Max 8 pages pour ne pas surcharger

    def _prioritize_emails(
        self, emails: list[str], site_domain: str = ""
    ) -> Optional[str]:
        """Choisit le meilleur email parmi les candidats, en favorisant le domaine du site."""
        if not emails:
            return None

        # Nettoyer le domaine du site pour comparaison
        site_domain = (
            site_domain.replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .split("/")[0]
            .lower()
        )

        # Séparer : emails du même domaine vs autres
        same_domain = [
            e
            for e in emails
            if site_domain and e.split("@")[-1].replace("www.", "") == site_domain
        ]
        other = [e for e in emails if e not in same_domain]

        # Priorité : contact@ > info@ > reservation@ > accueil@ > direction@ > autres
        priority_prefixes = [
            "contact",
            "info",
            "reservation",
            "accueil",
            "direction",
            "booking",
        ]

        # D'abord chercher dans les emails du même domaine
        for prefix in priority_prefixes:
            for email in same_domain:
                if email.startswith(prefix):
                    return email
        if same_domain:
            return same_domain[0]

        # Sinon dans les autres
        for prefix in priority_prefixes:
            for email in other:
                if email.startswith(prefix):
                    return email

        return emails[0]

    async def scrape(self, website_url: str) -> EnrichmentResult:
        """Scrape le site web d'un établissement — recherche approfondie d'email."""
        result = EnrichmentResult(source="website")
        all_emails = []
        all_phones = []

        try:
            logger.info(f"Scraping website: {website_url}")

            # ── Étape 1 : page d'accueil ──
            html = await self.scraper.fetch_page(website_url)
            if not html:
                result.error = "Impossible d'accéder au site"
                return result

            soup = BeautifulSoup(html, "lxml")

            # Emails via mailto: (le plus fiable)
            all_emails.extend(self._extract_mailto(soup))
            # Emails via regex
            all_emails.extend(self.scraper.extract_emails(html))
            # Téléphones
            all_phones.extend(self.scraper.extract_phones(html))

            # Réseaux sociaux
            social = self.scraper.extract_social_links(html, soup)
            result.facebook_url = social.get("facebook_url")
            result.instagram_url = social.get("instagram_url")
            result.linkedin_url = social.get("linkedin_url")

            # ── Étape 2 : liens internes qui mènent à "contact" ──
            contact_links = self._find_contact_links(soup, website_url)

            # ── Étape 3 : chemins classiques + liens trouvés ──
            pages_to_check = set()

            # Ajouter les chemins classiques
            for path in self.CONTACT_PATHS:
                pages_to_check.add(website_url.rstrip("/") + path)

            # Ajouter les liens internes trouvés
            for link_url in contact_links:
                pages_to_check.add(link_url)

            # Parcourir toutes les pages candidates
            for page_url in pages_to_check:
                if page_url == website_url.rstrip("/") or page_url == website_url:
                    continue  # Pas besoin de re-scraper l'accueil

                try:
                    page_html = await self.scraper.fetch_page(page_url)
                    if not page_html:
                        continue

                    page_soup = BeautifulSoup(page_html, "lxml")

                    # mailto: en priorité
                    all_emails.extend(self._extract_mailto(page_soup))
                    # regex
                    all_emails.extend(self.scraper.extract_emails(page_html))
                    # téléphones
                    all_phones.extend(self.scraper.extract_phones(page_html))

                    # Chercher des noms de dirigeants dans mentions légales
                    page_lower = page_url.lower()
                    if (
                        "mention" in page_lower
                        or "legal" in page_lower
                        or "cgu" in page_lower
                    ):
                        dirigeant_match = re.search(
                            r"(?:Directeur|Gérant|Responsable|Propriétaire)[:\s]+([A-ZÀ-Ü][a-zà-ü]+\s+[A-ZÀ-Ü][A-ZÀ-Üa-zà-ü]+)",
                            page_html,
                        )
                        if dirigeant_match:
                            name_parts = dirigeant_match.group(1).split()
                            contact = ContactInfo(
                                full_name=dirigeant_match.group(1),
                                first_name=name_parts[0] if name_parts else None,
                                last_name=" ".join(name_parts[1:])
                                if len(name_parts) > 1
                                else None,
                                role=ContactRole.DIRECTOR,
                                source="website_legal",
                                confidence=80,
                            )
                            result.contacts.append(contact)

                    # Si on a trouvé un email, on peut s'arrêter plus tôt
                    if all_emails:
                        break

                except Exception:
                    pass

            # ── Résultat final ──
            # Dédupliquer
            all_emails = list(set(e.lower() for e in all_emails))
            all_phones = list(set(all_phones))

            result.email = self._prioritize_emails(all_emails, website_url)
            result.phone = all_phones[0] if all_phones else None

            if all_emails:
                logger.info(f"Emails trouvés sur {website_url}: {all_emails}")
            else:
                logger.info(f"Aucun email trouvé sur {website_url}")

            result.success = bool(
                result.email or result.phone or result.facebook_url or result.contacts
            )
            return result

        except Exception as e:
            logger.error(f"Erreur scraping website: {e}")
            result.error = str(e)
            return result


class HunterIOClient:
    """Client pour l'API Hunter.io (PAYANT - optionnel)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.hunter.io/v2"
        self.client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        await self.client.aclose()

    async def domain_search(self, domain: str) -> EnrichmentResult:
        """Recherche les emails associés à un domaine."""
        result = EnrichmentResult(source="hunter.io")

        if not self.api_key:
            result.error = "Clé API Hunter.io non configurée (optionnel)"
            return result

        try:
            url = f"{self.base_url}/domain-search"
            params = {"domain": domain, "api_key": self.api_key}

            response = await self.client.get(url, params=params)
            data = response.json()

            if response.status_code != 200:
                result.error = data.get("errors", [{}])[0].get("details", "Erreur API")
                return result

            emails_data = data.get("data", {}).get("emails", [])

            for email_info in emails_data[:5]:
                contact = ContactInfo(
                    email=email_info.get("value"),
                    first_name=email_info.get("first_name"),
                    last_name=email_info.get("last_name"),
                    job_title=email_info.get("position"),
                    confidence=email_info.get("confidence", 0),
                    source="hunter.io",
                )

                position = (email_info.get("position") or "").lower()
                if any(
                    x in position
                    for x in ["directeur", "director", "gérant", "owner", "pdg", "ceo"]
                ):
                    contact.role = ContactRole.DIRECTOR
                elif any(x in position for x in ["marketing", "communication"]):
                    contact.role = ContactRole.MARKETING
                elif any(x in position for x in ["manager", "responsable"]):
                    contact.role = ContactRole.MANAGER

                if contact.first_name and contact.last_name:
                    contact.full_name = f"{contact.first_name} {contact.last_name}"

                result.contacts.append(contact)

            result.success = bool(result.contacts)
            return result

        except Exception as e:
            logger.error(f"Erreur Hunter.io: {e}")
            result.error = str(e)
            return result


class EnrichmentService:
    """Service principal d'enrichissement (utilise sources GRATUITES par défaut)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.web_scraper = WebScraper()
        self.website_scraper = WebsiteScraper(self.web_scraper)
        self.pagesjaunes = PagesJaunesScraper(self.web_scraper)
        self.google_search = GoogleSearchScraper(self.web_scraper)
        self.societe_com = SocieteComScraper(self.web_scraper)
        self.email_generator = EmailPatternGenerator()
        # API payantes (optionnelles)
        self.hunter = HunterIOClient(settings.hunter_api_key)

    async def close(self):
        await self.web_scraper.close()
        await self.hunter.close()

    async def enrich_lead(self, lead: Lead, use_paid_apis: bool = False) -> dict:
        """
        Enrichit un lead avec toutes les sources disponibles.

        Args:
            lead: Le lead à enrichir
            use_paid_apis: Si True, utilise aussi les APIs payantes (Hunter.io, etc.)
        """
        logger.info(f"Enrichissement du lead: {lead.name} (ID: {lead.id})")
        results = {}

        # === SOURCES GRATUITES ===

        # 1. Scraper le site web si disponible
        if lead.website:
            result = await self.website_scraper.scrape(lead.website)
            results["website"] = result

            if result.success:
                if result.phone and not lead.phone:
                    lead.phone = result.phone
                if result.email and not lead.email:
                    lead.email = result.email
                if result.facebook_url and not lead.facebook_url:
                    lead.facebook_url = result.facebook_url
                if result.instagram_url and not lead.instagram_url:
                    lead.instagram_url = result.instagram_url
                if result.linkedin_url and not lead.linkedin_url:
                    lead.linkedin_url = result.linkedin_url

                # Créer les contacts trouvés
                for contact_info in result.contacts:
                    await self._create_contact(lead, contact_info)

        # 2. PagesJaunes si pas d'email/téléphone
        if not lead.email or not lead.phone:
            result = await self.pagesjaunes.search(lead.name, lead.city)
            results["pagesjaunes"] = result

            if result.success:
                if result.phone and not lead.phone:
                    lead.phone = result.phone
                if result.email and not lead.email:
                    lead.email = result.email

        # 3. Societe.com pour trouver les dirigeants
        result = await self.societe_com.search_company(lead.name, lead.city)
        results["societe_com"] = result

        if result.success:
            for contact_info in result.contacts:
                # Générer les emails possibles pour le contact
                if lead.website and contact_info.first_name and contact_info.last_name:
                    domain = (
                        lead.website.replace("https://", "")
                        .replace("http://", "")
                        .replace("www.", "")
                        .split("/")[0]
                    )
                    generated_emails = self.email_generator.generate_emails(
                        domain, contact_info.first_name, contact_info.last_name
                    )
                    if generated_emails:
                        contact_info.email = generated_emails[0]["email"]
                        contact_info.confidence = generated_emails[0]["confidence"]

                await self._create_contact(lead, contact_info)

        # 4. Recherche Google si toujours pas d'email
        if not lead.email:
            result = await self.google_search.search_email_contact(lead.name, lead.city)
            results["google_search"] = result

            if result.success and result.email:
                lead.email = result.email
            if result.phone and not lead.phone:
                lead.phone = result.phone

        # 5. Générer des emails par pattern si on a un site mais pas d'email
        if lead.website and not lead.email:
            domain = (
                lead.website.replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .split("/")[0]
            )
            generated = self.email_generator.generate_emails(domain)
            if generated:
                # Prendre l'email générique avec la meilleure confiance
                lead.email = generated[0]["email"]
                results["email_pattern"] = EnrichmentResult(
                    source="email_pattern", success=True, email=lead.email
                )

        # === GOOGLE PLACES — source la plus fiable pour site web + avis ===
        from app.services.google_reviews_service import GoogleReviewsService

        gplaces = GoogleReviewsService()
        if gplaces.api_key:
            place_id = await gplaces.find_place_id(lead.name, lead.city, lead.address)
            if place_id:
                details = await gplaces.get_place_details(place_id)
                if details:
                    # Site web — source la plus fiable
                    gp_website = details.get("website")
                    if gp_website and not lead.website:
                        lead.website = gp_website
                        lead.has_website = True
                        logger.info(f"Site trouvé via Google Places: {gp_website}")
                        results["google_places_website"] = EnrichmentResult(
                            source="google_places", success=True, website=gp_website
                        )
                    # Avis Google
                    gp_rating = details.get("rating")
                    gp_reviews = details.get("user_ratings_total", 0)
                    if gp_rating:
                        lead.google_rating = gp_rating
                        lead.google_reviews_count = gp_reviews
                        logger.info(f"Avis Google: {gp_rating}/5 ({gp_reviews} avis)")
                    # Téléphone si absent
                    gp_phone = details.get("formatted_phone_number")
                    if gp_phone and not lead.phone:
                        lead.phone = gp_phone

        # === DÉTECTION ACTIVE DU SITE WEB — fallback DuckDuckGo ===
        # Seulement si Google Places n'a rien trouvé
        if not lead.website and lead.has_website is None:
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
                    f"Site trouvé via DuckDuckGo: {found.url} (confiance: {found.confidence})"
                )
                results["web_search"] = EnrichmentResult(
                    source="web_search", success=True, website=found.url
                )
            else:
                # Ni Google Places ni DuckDuckGo n'ont trouvé — on reste sur "inconnu"
                logger.info(f"Aucun site trouvé pour {lead.name} — statut inconnu")

        # === SECOND PASSAGE : scraper le site web si trouvé après le 1er passage ===
        # (Google Places ou DuckDuckGo a trouvé le site, mais on ne l'avait pas encore scrapé)
        if lead.website and not lead.email and "website" not in results:
            logger.info(f"Second passage scraping: {lead.website}")
            result = await self.website_scraper.scrape(lead.website)
            results["website_2nd_pass"] = result
            if result.success:
                if result.email and not lead.email:
                    lead.email = result.email
                if result.phone and not lead.phone:
                    lead.phone = result.phone
                if result.facebook_url and not lead.facebook_url:
                    lead.facebook_url = result.facebook_url
                if result.instagram_url and not lead.instagram_url:
                    lead.instagram_url = result.instagram_url
                for contact_info in result.contacts:
                    await self._create_contact(lead, contact_info)

        # === ANALYSE QUALITÉ DU SITE WEB ===
        if lead.website:
            analyzer = WebsiteAnalyzer()
            try:
                analysis = await analyzer.analyze(lead.website)
                if analysis.success:
                    lead.has_website = True
                    lead.website_quality_score = analysis.quality_score
                    lead.seo_score = analysis.seo_score
                    lead.geo_score = analysis.geo_score
                    lead.is_mobile_friendly = analysis.is_mobile_friendly
                    lead.has_booking_system = analysis.has_booking_system
                    if analysis.booking_platforms:
                        lead.booking_platform = ", ".join(
                            analysis.booking_platforms[:3]
                        )
                    logger.info(
                        f"Site analysé: qualité={analysis.quality_score}, SEO={analysis.seo_score}, GEO={analysis.geo_score}"
                    )
                else:
                    # Site inaccessible au moment de l'analyse (SSL, DNS, timeout, 4xx, 5xx...)
                    # On garde has_website=True car l'URL est connue — inaccessible ≠ inexistant
                    lead.has_website = True
                    logger.warning(
                        f"Site inaccessible mais URL connue: {lead.website} — {analysis.error}"
                    )
            except Exception as e:
                logger.error(f"Erreur analyse site {lead.website}: {e}")
            finally:
                await analyzer.close()

        # === SOURCES PAYANTES (optionnelles) ===
        if use_paid_apis and lead.website and settings.hunter_api_key:
            domain = (
                lead.website.replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .split("/")[0]
            )
            result = await self.hunter.domain_search(domain)
            results["hunter"] = result

            for contact_info in result.contacts:
                await self._create_contact(lead, contact_info)

        # === ENRICHISSEMENT NOUVELLES ENTREPRISES (BODACC) ===
        if lead.is_nouvelle_entreprise and (lead.siren or lead.external_id):
            if not lead.bodacc_activite:
                try:
                    from app.services.bodacc_service import BodaccService

                    bodacc = BodaccService()
                    await bodacc.enrich_lead(lead, self.db)
                    await bodacc.close()
                except Exception as e:
                    logger.warning(f"Erreur enrichissement BODACC: {e}")

            # Recalculer le score RCS
            lead.update_rcs_score()

        # Mettre à jour le statut
        lead.enriched_at = datetime.utcnow()
        if lead.status == LeadStatus.NEW:
            lead.status = LeadStatus.ENRICHED

        lead.update_score()
        await self.db.commit()

        # Compter les contacts créés
        contacts_result = await self.db.execute(
            select(Contact).where(Contact.lead_id == lead.id)
        )
        contacts_count = len(contacts_result.scalars().all())

        return {
            "lead_id": lead.id,
            "lead_name": lead.name,
            "sources": {
                k: {"success": v.success, "error": v.error} for k, v in results.items()
            },
            "enriched_data": {
                "phone": lead.phone,
                "email": lead.email,
                "facebook_url": lead.facebook_url,
                "instagram_url": lead.instagram_url,
                "linkedin_url": lead.linkedin_url,
            },
            "contacts_found": contacts_count,
        }

    async def _create_contact(
        self, lead: Lead, contact_info: ContactInfo
    ) -> Optional[Contact]:
        """Crée un contact à partir des infos trouvées."""
        if not contact_info.email and not contact_info.full_name:
            return None

        # Vérifier si le contact existe déjà
        if contact_info.email:
            existing = await self.db.execute(
                select(Contact).where(
                    Contact.lead_id == lead.id, Contact.email == contact_info.email
                )
            )
            if existing.scalar_one_or_none():
                return None

        if contact_info.full_name:
            existing = await self.db.execute(
                select(Contact).where(
                    Contact.lead_id == lead.id,
                    Contact.full_name == contact_info.full_name,
                )
            )
            if existing.scalar_one_or_none():
                return None

        contact = Contact(
            lead_id=lead.id,
            first_name=contact_info.first_name,
            last_name=contact_info.last_name,
            full_name=contact_info.full_name,
            email=contact_info.email,
            phone=contact_info.phone,
            job_title=contact_info.job_title,
            role=contact_info.role,
            linkedin_url=contact_info.linkedin_url,
            source=contact_info.source,
            email_confidence=contact_info.confidence,
        )

        self.db.add(contact)
        logger.info(
            f"Contact créé: {contact.full_name or contact.email} pour {lead.name}"
        )
        return contact

    async def enrich_leads_batch(
        self,
        lead_ids: Optional[list[int]] = None,
        limit: int = 10,
        status_filter: LeadStatus = LeadStatus.NEW,
        use_paid_apis: bool = False,
    ) -> dict:
        """Enrichit plusieurs leads en batch."""
        query = select(Lead)

        if lead_ids:
            query = query.where(Lead.id.in_(lead_ids))
        else:
            query = query.where(Lead.status == status_filter)

        query = query.limit(limit)

        result = await self.db.execute(query)
        leads = result.scalars().all()

        logger.info(
            f"Enrichissement de {len(leads)} leads (APIs payantes: {use_paid_apis})..."
        )

        results = []
        for lead in leads:
            try:
                enrichment_result = await self.enrich_lead(
                    lead, use_paid_apis=use_paid_apis
                )
                results.append(enrichment_result)
                await asyncio.sleep(2)  # Pause pour éviter le rate limiting
            except Exception as e:
                logger.error(f"Erreur enrichissement lead {lead.id}: {e}")
                results.append(
                    {"lead_id": lead.id, "lead_name": lead.name, "error": str(e)}
                )

        await self.close()

        return {
            "total": len(leads),
            "results": results,
        }


# Fonction helper
async def enrich_lead_by_id(
    db: AsyncSession, lead_id: int, use_paid_apis: bool = False
) -> dict:
    """Enrichit un lead par son ID."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()

    if not lead:
        return {"error": "Lead non trouvé"}

    service = EnrichmentService(db)
    try:
        return await service.enrich_lead(lead, use_paid_apis=use_paid_apis)
    finally:
        await service.close()
