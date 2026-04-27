"""
Service d'analyse des avis Google via l'API Google Places.

Ce service permet de :
- Rechercher le Place ID d'un établissement
- Récupérer les avis Google (note, nombre d'avis)
- Calculer la fréquence des avis (récurrence)
- Analyser la tendance (croissance/déclin)
"""

import httpx
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from loguru import logger

from app.config import get_settings


@dataclass
class GoogleReviewsData:
    """Données des avis Google pour un établissement."""

    place_id: str
    rating: float  # Note moyenne (1.0-5.0)
    reviews_count: int  # Nombre total d'avis
    period_months: int  # Période analysée
    frequency: float  # Avis par mois
    trend: str  # "growing", "stable", "declining"
    analyzed_at: datetime


class GoogleReviewsService:
    """Service pour analyser les avis Google d'un établissement."""

    BASE_URL = "https://maps.googleapis.com/maps/api/place"

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.google_places_api_key

    async def find_place_id(
        self, name: str, city: Optional[str] = None, address: Optional[str] = None
    ) -> Optional[str]:
        """
        Recherche le Place ID Google d'un établissement.

        Args:
            name: Nom de l'établissement
            city: Ville (optionnel, améliore la précision)
            address: Adresse complète (optionnel)

        Returns:
            Le Place ID ou None si non trouvé
        """
        if not self.api_key:
            logger.warning("Clé API Google Places non configurée")
            return None

        # Construire la requête de recherche
        query_parts = [name]
        if city:
            query_parts.append(city)
        if address:
            query_parts.append(address)

        query = " ".join(query_parts)

        url = f"{self.BASE_URL}/findplacefromtext/json"
        params = {
            "input": query,
            "inputtype": "textquery",
            "fields": "place_id,name,formatted_address",
            "key": self.api_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "OK" and data.get("candidates"):
                    place_id = data["candidates"][0].get("place_id")
                    logger.info(f"Place ID trouvé pour '{name}': {place_id}")
                    return place_id
                else:
                    logger.warning(f"Aucun résultat Google Places pour '{name}'")
                    return None

        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP lors de la recherche Place ID: {e}")
            return None

    async def get_place_details(self, place_id: str) -> Optional[dict]:
        """
        Récupère les détails d'un lieu (note, nombre d'avis, avis récents).

        Args:
            place_id: L'identifiant Google Places

        Returns:
            Dictionnaire avec rating, user_ratings_total, reviews
        """
        if not self.api_key:
            logger.warning("Clé API Google Places non configurée")
            return None

        url = f"{self.BASE_URL}/details/json"
        params = {
            "place_id": place_id,
            "fields": "rating,user_ratings_total,reviews,website,formatted_phone_number",
            "reviews_sort": "newest",
            "key": self.api_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "OK" and data.get("result"):
                    return data["result"]
                else:
                    logger.warning(
                        f"Impossible de récupérer les détails pour {place_id}"
                    )
                    return None

        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP lors de la récupération des détails: {e}")
            return None

    def calculate_reviews_metrics(
        self, place_id: str, rating: float, reviews_count: int, reviews: list[dict]
    ) -> GoogleReviewsData:
        """
        Calcule les métriques de récurrence et tendance des avis.

        Args:
            place_id: ID Google Places
            rating: Note moyenne
            reviews_count: Nombre total d'avis
            reviews: Liste des avis récents (max 5 via API)

        Returns:
            GoogleReviewsData avec toutes les métriques calculées
        """
        now = datetime.now()

        # Cas sans avis ou très peu d'avis
        if reviews_count == 0 or not reviews:
            return GoogleReviewsData(
                place_id=place_id,
                rating=rating,
                reviews_count=reviews_count,
                period_months=0,
                frequency=0.0,
                trend="stable",
                analyzed_at=now,
            )

        # Extraire les timestamps des avis (triés du plus récent au plus ancien)
        timestamps = sorted(
            [r.get("time", 0) for r in reviews if r.get("time")], reverse=True
        )

        if not timestamps:
            return GoogleReviewsData(
                place_id=place_id,
                rating=rating,
                reviews_count=reviews_count,
                period_months=12,  # Estimation par défaut
                frequency=reviews_count / 12,
                trend="stable",
                analyzed_at=now,
            )

        # Calculer la période basée sur les avis disponibles
        newest_review = datetime.fromtimestamp(timestamps[0])
        oldest_review = datetime.fromtimestamp(timestamps[-1])

        # Période entre le plus ancien avis disponible et maintenant
        days_span = (now - oldest_review).days
        months_from_reviews = max(1, days_span / 30)

        # Estimer la période totale en extrapolant
        # Si on a 5 avis sur X mois, et Y avis au total, période ≈ X * (Y / 5)
        if len(timestamps) > 1:
            ratio = reviews_count / len(timestamps)
            period_months = int(months_from_reviews * ratio)
        else:
            # Un seul avis avec timestamp : estimation grossière
            period_months = max(1, int(reviews_count / 2))  # ~2 avis/mois par défaut

        # Plafonner à des valeurs raisonnables (1-120 mois = 10 ans max)
        period_months = max(1, min(period_months, 120))

        # Calculer la fréquence (avis par mois)
        frequency = round(reviews_count / period_months, 2)

        # Calculer la tendance en comparant les intervalles entre avis
        trend = self._calculate_trend(timestamps)

        return GoogleReviewsData(
            place_id=place_id,
            rating=rating,
            reviews_count=reviews_count,
            period_months=period_months,
            frequency=frequency,
            trend=trend,
            analyzed_at=now,
        )

    def _calculate_trend(self, timestamps: list[int]) -> str:
        """
        Détermine la tendance des avis (croissance/stable/déclin).

        Logique : compare l'intervalle entre les avis récents vs anciens.
        - Si les avis récents sont plus rapprochés → "growing"
        - Si les avis récents sont plus espacés → "declining"
        - Sinon → "stable"

        Args:
            timestamps: Liste des timestamps Unix triés (récent → ancien)

        Returns:
            "growing", "stable", ou "declining"
        """
        if len(timestamps) < 3:
            return "stable"  # Pas assez de données

        # Calculer les intervalles entre avis consécutifs (en jours)
        intervals = []
        for i in range(len(timestamps) - 1):
            diff_seconds = timestamps[i] - timestamps[i + 1]
            diff_days = diff_seconds / 86400  # Convertir en jours
            intervals.append(diff_days)

        # Séparer en intervalles "récents" et "anciens"
        mid = len(intervals) // 2
        recent_intervals = intervals[:mid] if mid > 0 else intervals[:1]
        older_intervals = intervals[mid:] if mid > 0 else intervals[1:]

        if not recent_intervals or not older_intervals:
            return "stable"

        # Calculer les moyennes
        avg_recent = sum(recent_intervals) / len(recent_intervals)
        avg_older = sum(older_intervals) / len(older_intervals)

        # Comparer : si intervalle récent < ancien de plus de 20% → growing
        if avg_older > 0:
            ratio = avg_recent / avg_older
            if ratio < 0.8:  # Avis récents 20% plus rapprochés
                return "growing"
            elif ratio > 1.2:  # Avis récents 20% plus espacés
                return "declining"

        return "stable"

    async def analyze_establishment(
        self,
        name: str,
        city: Optional[str] = None,
        address: Optional[str] = None,
        place_id: Optional[str] = None,
    ) -> Optional[GoogleReviewsData]:
        """
        Analyse complète des avis Google d'un établissement.

        Args:
            name: Nom de l'établissement
            city: Ville (optionnel)
            address: Adresse (optionnel)
            place_id: Place ID si déjà connu (optionnel)

        Returns:
            GoogleReviewsData ou None si analyse impossible
        """
        # 1. Trouver le Place ID si pas fourni
        if not place_id:
            place_id = await self.find_place_id(name, city, address)
            if not place_id:
                return None

        # 2. Récupérer les détails
        details = await self.get_place_details(place_id)
        if not details:
            return None

        rating = details.get("rating", 0.0)
        reviews_count = details.get("user_ratings_total", 0)
        reviews = details.get("reviews", [])

        # 3. Calculer les métriques
        return self.calculate_reviews_metrics(
            place_id=place_id,
            rating=rating,
            reviews_count=reviews_count,
            reviews=reviews,
        )


# Instance singleton
_service: Optional[GoogleReviewsService] = None


def get_google_reviews_service() -> GoogleReviewsService:
    """Retourne l'instance du service Google Reviews."""
    global _service
    if _service is None:
        _service = GoogleReviewsService()
    return _service
