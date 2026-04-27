"""
Service DataForSEO - Analyse SEO réelle d'un domaine via l'API DataForSEO.

Contrairement au scoring HTML local (qui analyse le code de la page),
DataForSEO fournit des métriques basées sur l'index réel de Google :
- Nombre de mots-clés positionnés
- Trafic organique estimé
- Autorité de domaine (domain rank)

Un site avec 0 mot-clé positionné = prospect idéal pour Kawanah Tourisme.

Documentation : https://docs.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live/
Auth : HTTP Basic (login:password encodé en base64)
"""

import base64
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger

from app.config import get_settings

settings = get_settings()

# Paramètres France
LOCATION_CODE_FRANCE = 2250
LANGUAGE_CODE_FR = "fr"


@dataclass
class DomainSEOMetrics:
    """Métriques SEO d'un domaine depuis DataForSEO."""

    success: bool = False
    domain: str = ""

    # Métriques organiques Google
    domain_rank: int = 0  # Score d'autorité 0-100 (DataForSEO)
    organic_keywords: int = 0  # Nombre de mots-clés positionnés sur Google
    organic_traffic: int = 0  # Trafic organique mensuel estimé (ETV)
    paid_keywords: int = 0  # Mots-clés en SEA (Google Ads)

    # Interprétation
    seo_presence: str = "unknown"  # "none", "weak", "moderate", "strong"
    opportunity_score: int = 0  # Score d'opportunité pour Kawanah (0-100)

    error: Optional[str] = None


class DataForSEOClient:
    """
    Client pour l'API DataForSEO.
    Utilise l'endpoint Domain Rank Overview (live) pour obtenir
    les métriques SEO réelles d'un domaine.
    """

    BASE_URL = "https://api.dataforseo.com/v3"

    def __init__(self, login: str, password: str):
        credentials = base64.b64encode(f"{login}:{password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=30.0, headers=self.headers)

    async def close(self):
        await self.client.aclose()

    def _extract_domain(self, url: str) -> str:
        """Extrait le domaine depuis une URL complète."""
        domain = url.strip()
        domain = domain.replace("https://", "").replace("http://", "")
        domain = domain.replace("www.", "")
        domain = domain.split("/")[0].split("?")[0]
        return domain.lower()

    async def get_domain_metrics(self, url: str) -> DomainSEOMetrics:
        """
        Récupère les métriques SEO d'un domaine.

        Args:
            url: URL ou domaine de l'établissement (ex: "hotel-paris.fr")

        Returns:
            DomainSEOMetrics avec les données organiques Google
        """
        domain = self._extract_domain(url)
        result = DomainSEOMetrics(domain=domain)

        if not settings.dataforseo_login or not settings.dataforseo_password:
            result.error = "Credentials DataForSEO non configurés"
            return result

        try:
            logger.info(f"DataForSEO: analyse de {domain}")

            response = await self.client.post(
                f"{self.BASE_URL}/dataforseo_labs/google/domain_rank_overview/live",
                json=[
                    {
                        "target": domain,
                        "location_code": LOCATION_CODE_FRANCE,
                        "language_code": LANGUAGE_CODE_FR,
                    }
                ],
            )

            data = response.json()

            # Vérifier le statut global
            if data.get("status_code") != 20000:
                result.error = (
                    f"Erreur API: {data.get('status_message', 'Unknown error')}"
                )
                return result

            # Parser la réponse
            tasks = data.get("tasks", [])
            if not tasks:
                result.error = "Pas de résultat retourné"
                return result

            task = tasks[0]
            if task.get("status_code") != 20000:
                result.error = (
                    f"Erreur tâche: {task.get('status_message', 'Task error')}"
                )
                return result

            task_results = task.get("result", [])
            if not task_results:
                # Domaine inconnu = aucune présence SEO
                result.success = True
                result.seo_presence = "none"
                result.opportunity_score = 90
                logger.info(f"DataForSEO: {domain} = aucune présence SEO connue")
                return result

            raw = task_results[0]
            metrics_organic = raw.get("metrics", {}).get("organic", {})
            metrics_paid = raw.get("metrics", {}).get("paid", {})

            result.domain_rank = raw.get("domain_rank", 0) or 0
            result.organic_keywords = metrics_organic.get("count", 0) or 0
            result.organic_traffic = metrics_organic.get("etv", 0) or 0
            result.paid_keywords = metrics_paid.get("count", 0) or 0

            result.seo_presence = self._classify_seo_presence(result)
            result.opportunity_score = self._calculate_opportunity_score(result)
            result.success = True

            logger.info(
                f"DataForSEO: {domain} — rank={result.domain_rank}, "
                f"keywords={result.organic_keywords}, traffic={result.organic_traffic}, "
                f"opportunité={result.opportunity_score}"
            )
            return result

        except httpx.TimeoutException:
            result.error = "Timeout DataForSEO"
            logger.warning(f"DataForSEO timeout pour {domain}")
            return result
        except Exception as e:
            result.error = str(e)
            logger.error(f"Erreur DataForSEO pour {domain}: {e}")
            return result

    def _classify_seo_presence(self, metrics: DomainSEOMetrics) -> str:
        """Classifie la présence SEO du domaine."""
        if metrics.organic_keywords == 0 and metrics.domain_rank == 0:
            return "none"
        elif metrics.organic_keywords < 10 or metrics.domain_rank < 10:
            return "weak"
        elif metrics.organic_keywords < 100 or metrics.domain_rank < 30:
            return "moderate"
        else:
            return "strong"

    def _calculate_opportunity_score(self, metrics: DomainSEOMetrics) -> int:
        """
        Calcule le score d'opportunité commerciale pour Kawanah Tourisme.
        Plus le score est élevé, plus l'établissement a besoin de nos services SEO/GEO.

        Score inversement proportionnel à la présence SEO.
        """
        score = 0

        # Pas de mots-clés = site invisible sur Google
        if metrics.organic_keywords == 0:
            score += 40
        elif metrics.organic_keywords < 10:
            score += 30
        elif metrics.organic_keywords < 50:
            score += 20
        elif metrics.organic_keywords < 200:
            score += 10

        # Trafic organique quasi nul
        if metrics.organic_traffic == 0:
            score += 30
        elif metrics.organic_traffic < 100:
            score += 20
        elif metrics.organic_traffic < 500:
            score += 10

        # Faible autorité de domaine
        if metrics.domain_rank == 0:
            score += 20
        elif metrics.domain_rank < 10:
            score += 15
        elif metrics.domain_rank < 20:
            score += 8

        return min(score, 100)


async def analyze_domain(url: str) -> DomainSEOMetrics:
    """Helper : analyse le domaine d'un lead."""
    client = DataForSEOClient(
        login=settings.dataforseo_login,
        password=settings.dataforseo_password,
    )
    try:
        return await client.get_domain_metrics(url)
    finally:
        await client.close()
