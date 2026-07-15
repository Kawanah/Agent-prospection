"""
Service de génération de messages avec l'IA (Claude API).
Génère des emails personnalisés selon le profil du prospect.
"""

import re
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from anthropic import Anthropic
from loguru import logger

from app.config import get_settings
from app.models.lead import Lead, WebsiteMatchStatus
from app.services.ai_context import (
    get_regional_context,
    get_seasonal_context,
    get_type_label,
)

settings = get_settings()


class MessageChannel(str, Enum):
    """Canal de communication."""

    EMAIL = "email"
    LINKEDIN = "linkedin"


class MessageTone(str, Enum):
    """Ton du message."""

    PROFESSIONAL = "professional"  # Formel, corporate
    FRIENDLY = "friendly"  # Chaleureux, accessible
    DIRECT = "direct"  # Court, droit au but


@dataclass
class GeneratedMessage:
    """Message généré par l'IA."""

    subject: str
    body: str
    channel: MessageChannel
    tone: MessageTone
    lead_segment: str
    personalization_points: list[str]


class MessageTemplates:
    """
    Stratégies de message par segment.

    Voix : Laetitia, experte web hospitalité. Ton concret, sûr, qui donne envie.
    Structure : constat d'audit → enjeu business → ce que Kawanah apporte → rendez-vous.
    Vendeur mais crédible : on s'appuie sur de vrais constats, jamais sur du baratin.
    """

    OFFER_CONTEXT = """
OFFRE KAWANAH TOURISME (à utiliser comme arguments concrets, pas comme catalogue) :
- Création de sites internet pour le tourisme : hôtels, gîtes, chambres d'hôtes, campings, hébergements.
- Différenciateur unique : un socle SEO et IA natif intégré dès la conception. Le site est compris,
  indexé et recommandé par Google ET par les moteurs de réponse IA (ChatGPT, Perplexity, etc.).
- Sites responsives, modernes et dynamiques, qui mettent le lieu en valeur (photos, ambiance, expérience).
- Fonctionnalités qui convertissent selon le type de prospect : formulaire de contact, demande d'inscription,
  demande de devis, réservation en direct quand elle est réellement pertinente, carte d'accès,
  avis clients mis en avant, navigation claire et rapide.
- Réservation directe : uniquement pour les hébergements ou activités où une réservation est explicitement détectée.

UTILISATION DANS LES EMAILS :
Choisir l'angle qui correspond au lead et à son audit. Nommer un ou deux manques concrets du site,
montrer ce que ça coûte en demandes, inscriptions, contacts ou réservations selon le cas, puis ce que Kawanah met en face.
Vendeur, pas agressif.
"""

    # ─── Règles de style globales injectées dans chaque prompt ────────────────
    STYLE_RULES = """
RÈGLES DE STYLE ABSOLUES (à respecter impérativement) :
- Tu écris un BROUILLON de prospection que Laetitia relira avant envoi
- Voix de Laetitia : experte web hospitalité, ton chaleureux, valorisant et convaincant. On donne envie, on ne fait jamais la leçon
- Méthode AIDA en version DOUCE (Attention, Intérêt, Désir, Action) :
  1. Bonjour,
  2. ATTENTION : "J'ai découvert votre site : [URL]" puis un compliment sincère sur l'établissement et ce qu'il propose. Enchaîner : "votre présence en ligne ne reflète pas encore pleinement la qualité de l'expérience que vous offrez"
  3. INTÉRÊT : rappeler que la plupart des visiteurs découvrent un établissement depuis leur smartphone, puis présenter 2 ou 3 constats de l'audit comme un POTENTIEL à révéler, jamais comme un défaut (ex : "votre site n'est pas encore optimisé pour les mobiles", "son design gagnerait à être rafraîchi"). Tournures douces : "pas encore", "gagnerait à", "mérite"
  4. DÉSIR : "Imaginez un site qui permette à vos visiteurs de..." puis les bénéfices concrets adaptés au prospect (trouver les infos pratiques, s'inscrire ou contacter facilement, réserver seulement si pertinent, lire les avis qui rassurent, découvrir un univers moderne)
  5. Le différenciateur Kawanah : sites modernes et responsives, avec un socle SEO et IA natif (visibles sur Google ET sur les moteurs IA type ChatGPT). Objectif : transformer plus de visiteurs en demandes, inscriptions, contacts ou réservations selon le cas
  6. ACTION : proposition courte ("je peux vous montrer en 15 minutes à quoi pourrait ressembler une nouvelle version du site de [nom]"), puis la phrase de rendez-vous exacte, formule de politesse et signature
- TOUJOURS commencer par "Bonjour," sur une ligne seule
- TOUJOURS citer l'URL du site juste après "J'ai découvert votre site :"
- TOUJOURS s'appuyer sur les constats réels de l'AUDIT CONCRET fourni. Ne rien inventer qui n'y figure pas
- INTERDICTION d'affirmer qu'il existe ou manque une réservation, une plateforme tierce ou un parcours de réservation si ce n'est pas explicitement détecté
- Pour un club, une association, un loisir ou une activité sportive, parler plutôt d'inscription, de demande de contact, d'informations pratiques, d'horaires, de lieu, d'avis et de visibilité locale. Ne pas parler de réservation sauf preuve explicite
- Convaincre par la valorisation et le bénéfice, jamais par la peur ou le reproche
- INTERDICTION de dénigrer ou de mettre le prospect à l'index : on ne dit jamais que son site est "mauvais", "nul", "dépassé", "à la traîne". On parle de potentiel, de mise à niveau, d'opportunité
- JAMAIS de guillemets « » ou " " dans le message
- INTERDICTION ABSOLUE du tiret long (em dash). Ne jamais l'utiliser. Virgule, point ou reformulation à la place
- JAMAIS "Je me permets de vous contacter"
- JAMAIS nommer une plateforme tierce (Booking, Airbnb...) : dire "un intermédiaire" / "une plateforme tierce"
- JAMAIS de chiffre en euros ou en pourcentage (pas de commission chiffrée)
- Le corps fait 8 à 12 lignes maximum hors signature. Convaincant mais pas un pavé
- Avant la formule de politesse, TOUJOURS cette phrase exacte sur sa propre ligne : "On peut prendre un rendez-vous pour en parler : " suivie du lien de rendez-vous
- Terminer par une formule de politesse courte (ex : "Belle journée,") puis la signature
- Signature : Laetitia pour Kawanah Tourisme\nhttps://tourisme.kawanah.com/
"""

    SANS_SITE = """
SITUATION : L'établissement n'a pas de site web.

ANGLE :
Dire simplement que tu n'as pas trouvé de site propre associé à l'établissement.
Rester prudent : peut-être que c'est volontaire, peut-être que c'est prévu plus tard.
La question doit ouvrir la discussion, pas pousser une solution.
"""

    A_VERIFIER = """
SITUATION : Le site semble inaccessible ou cassé.

ANGLE :
Signaler l'erreur comme une information utile, sans dramatiser.
Le message doit ressembler à une alerte courte entre professionnels.
Demander si c'est déjà connu de leur côté.
"""

    CHAUD = """
SITUATION : Le site existe mais la qualité est faible (SEO mauvais, design daté, pas mobile-friendly).

ANGLE :
Partir d'une observation concrète : présence Google faible, site daté, mobile difficile ou réservation indirecte.
Ne jamais faire peur. Dire que c'est un point à regarder, pas un problème grave.
Finir par demander si le sujet est déjà identifié chez eux.
"""

    TIEDE_GEO = """
SITUATION : Le site est correct, le SEO Google est OK, mais la présence sur les moteurs IA est absente.

ANGLE :
Commencer par reconnaître ce qui est déjà bien.
Introduire les moteurs IA comme une curiosité à vérifier, pas comme une urgence.
Proposer de partager une observation si le sujet les intéresse.
"""

    FROID_GEO = """
SITUATION : Le site est bon, le SEO est solide.

ANGLE :
Compliment factuel, puis une seule question sur les recherches IA.
Le message doit rester optionnel et léger.
Ne pas transformer une bonne situation en problème.
"""

    SITE_OBSOLETE = """
SITUATION : L'établissement a un site web, mais il est clairement obsolète / daté / amateur.

ANGLE :
Dire que le site semble ne plus refléter complètement l'établissement.
Ne pas juger le design. Parler de décalage possible entre l'expérience réelle et l'image en ligne.
Demander si une mise à jour du site est déjà prévue.
"""

    SITE_WIX = """
SITUATION : L'établissement a un site hébergé sur Wix avec une URL non personnalisée, par exemple wixsite.com.

ANGLE :
Ne pas critiquer Wix frontalement et ne pas parler d'adresse comme un défaut humiliant.
L'angle principal : le lieu semble déjà apprécié, mais le site mérite une mise à niveau technique pour passer à l'échelle.
Parler de meilleure navigation client, de mise en valeur du lieu, et de réservation directe.
Faire le lien avec les avis clients : le site devrait refléter la qualité perçue par leurs visiteurs.
Finir par demander si une évolution du site fait partie de leurs sujets du moment.
"""

    PLATEFORME_GITE = """
SITUATION : Établissement référencé sur une plateforme de gîtes (Gîtes de France, gites.fr, Clévacances...).

ANGLE :
Reconnaître la plateforme comme un vrai point positif.
Ouvrir doucement le sujet de la présence en propre, en complément.
Ne jamais critiquer la plateforme.
"""

    PAS_DE_RESA_DIRECTE = """
SITUATION : L'établissement a un site web, mais AUCUN système de réservation en direct. Le visiteur est redirigé vers une plateforme tierce.

RÈGLES IMPÉRATIVES :
- NE JAMAIS nommer la plateforme tierce (pas de "Booking", "Airbnb"). Dire "une plateforme tierce" ou "un intermédiaire".
- NE JAMAIS chiffrer en euros ou en pourcentage. Pas de "15-25%".
- NE JAMAIS être péjoratif. C'est une observation factuelle, pas un problème.

ANGLE :
Constater la redirection vers un intermédiaire sans le nommer.
Présenter la réservation directe comme un sujet possible, pas comme une obligation.
Questionner simplement leur réflexion actuelle.
"""

    NOUVELLE_STRUCTURE = """
SITUATION : Établissement qui vient d'ouvrir (date de création INSEE récente, moins de 18 mois).

ANGLE :
Commencer par une vraie félicitation, courte et sobre.
Parler des premiers mois comme d'un moment où la présence en ligne se construit naturellement.
Demander où ils en sont, sans urgence artificielle.
"""

    @classmethod
    def get_template(cls, lead: Lead) -> str:
        """
        Retourne le template approprié selon l'argument fort #1 du lead.

        Logique :
        1. Détecter les arguments forts (triés par impact)
        2. L'argument #1 dicte le template, c'est l'angle d'attaque du message
        3. Fallback sur le segment classique si aucun argument fort
        """
        from app.services.ai_service import AIService

        priority = lead.priority_level

        # ── Détection nouvelle structure ──
        from datetime import date

        is_new = False
        if lead.established_date:
            months_old = ((date.today() - lead.established_date).days) / 30
            is_new = months_old <= 18
        else:
            reviews = lead.google_reviews_count or 0
            is_new = reviews < 15 and lead.has_website in (None, False)

        # ── Détection plateforme gîte ──
        name_lower = (lead.name or "").lower()
        website_lower = (lead.website or "").lower()
        is_plateforme_gite = any(
            kw in name_lower or kw in website_lower
            for kw in [
                "gîte de france",
                "gites de france",
                "gîtes de france",
                "gites.fr",
                "clevacances",
                "clévacances",
            ]
        )

        if is_plateforme_gite:
            return cls.PLATEFORME_GITE

        # ── Arguments forts : l'argument #1 pilote le template ──
        strong_args = AIService._detect_strong_arguments(lead)
        top_key = strong_args[0]["key"] if strong_args else None

        # Site obsolète = argument massue → template dédié (priorité maximale)
        if top_key == "site_wix_sans_domaine":
            return cls.SITE_WIX

        # Site obsolète = argument fort → template dédié
        if top_key in ("site_obsolete_critique", "site_obsolete", "site_vieillissant"):
            return cls.SITE_OBSOLETE

        # Site cassé / inaccessible
        if top_key == "site_casse":
            return cls.A_VERIFIER

        # Pas de site du tout
        if top_key == "sans_site":
            if is_new:
                return cls.NOUVELLE_STRUCTURE
            return cls.SANS_SITE

        # Invisible sur Google (0 keywords, 0 trafic)
        if top_key in ("google_invisible", "google_faible", "zero_trafic"):
            return cls.CHAUD

        # Pas de réservation directe (seulement si c'est l'argument #1,
        # pas quand le site est obsolète ET sans résa)
        if top_key == "pas_resa_directe":
            return cls.PAS_DE_RESA_DIRECTE

        # Pas mobile-friendly, mauvais SEO → CHAUD
        if top_key in ("pas_mobile", "mauvais_seo"):
            return cls.CHAUD

        # Invisible IA (GEO)
        if top_key == "invisible_ia":
            return cls.TIEDE_GEO

        # ── Fallback classique (aucun argument fort détecté) ──
        if is_new and "SANS SITE" in priority:
            return cls.NOUVELLE_STRUCTURE
        elif "SANS SITE" in priority:
            return cls.SANS_SITE
        elif "VÉRIFIER" in priority:
            return cls.A_VERIFIER
        elif "CHAUD" in priority:
            return cls.CHAUD
        elif "TIÈDE" in priority:
            return cls.TIEDE_GEO
        else:
            return cls.FROID_GEO


class AIService:
    """Service de génération de messages avec Claude."""

    def __init__(self):
        self.client = None
        if settings.anthropic_api_key and settings.anthropic_api_key != "sk-ant-xxxxx":
            self.client = Anthropic(api_key=settings.anthropic_api_key)

    @staticmethod
    def _get_seasonal_context() -> dict:
        """Retourne le contexte saisonnier du mois courant pour personnaliser les messages."""
        return get_seasonal_context()

    @staticmethod
    def _detect_strong_arguments(lead: Lead) -> list[dict]:
        """
        Analyse un lead et retourne ses arguments forts, triés par impact.
        Chaque argument : { "key": str, "weight": int, "label": str, "hook": str }
        - label : nom court de l'argument
        - hook : phrase d'accroche percutante à utiliser dans le message
        """
        args = []
        lead_type = lead.lead_type.value if lead.lead_type else "other"
        type_label = {
            "hotel": "hôtel",
            "camping": "camping",
            "gite": "gîte",
            "chambre_hotes": "chambre d'hôtes",
            "residence": "résidence",
            "activite": "prestataire d'activités",
            "other": "établissement",
        }.get(lead_type, "établissement")
        city = lead.city or "votre ville"
        name = lead.name
        website_lower = (lead.website or "").lower()

        # ── 0. URL Wix non personnalisée : signal visible immédiatement ──
        if "wixsite.com" in website_lower:
            args.append(
                {
                    "key": "site_wix_sans_domaine",
                    "weight": 98,
                    "label": "Adresse Wix non personnalisée",
                    "hook": f"Le site de {name} utilise une adresse wixsite.com - avant même le contenu, "
                    "cela donne une impression moins professionnelle qu'un nom de domaine propre.",
                }
            )

        # ── 1. SITE OBSOLÈTE (quality < 40, site existant) ──
        if lead.has_website is True and lead.website_quality_score is not None:
            if lead.website_quality_score < 25:
                args.append(
                    {
                        "key": "site_obsolete_critique",
                        "weight": 95,
                        "label": "Site complètement obsolète",
                        "hook": f"Le site de {name} a besoin d'une refonte complète, design daté, "
                        f"pas aux standards actuels. Un voyageur qui arrive dessus repart immédiatement.",
                    }
                )
            elif lead.website_quality_score < 40:
                args.append(
                    {
                        "key": "site_obsolete",
                        "weight": 90,
                        "label": "Site obsolète",
                        "hook": f"Le site de {name} accuse son âge, il ne reflète pas la qualité "
                        f"de l'établissement. Première impression en ligne = décision de réserver ou non.",
                    }
                )
            elif lead.website_quality_score < 60:
                args.append(
                    {
                        "key": "site_vieillissant",
                        "weight": 60,
                        "label": "Site vieillissant",
                        "hook": f"Le site de {name} fait le job mais commence à dater face à la concurrence.",
                    }
                )

        # ── 2. PAS DE SITE DU TOUT ──
        if lead.has_website is False:
            args.append(
                {
                    "key": "sans_site",
                    "weight": 88,
                    "label": "Aucun site web",
                    "hook": f"Impossible de trouver {name} en ligne, les voyageurs qui cherchent "
                    f"un {type_label} à {city} ne vous trouvent tout simplement pas.",
                }
            )

        # ── 3. INVISIBLE SUR GOOGLE (0 mots-clés) ──
        if lead.dataforseo_organic_keywords is not None:
            if lead.dataforseo_organic_keywords == 0:
                args.append(
                    {
                        "key": "google_invisible",
                        "weight": 85,
                        "label": "Invisible sur Google",
                        "hook": f"0 mot-clé positionné sur Google, {name} n'existe pas dans les résultats "
                        f"de recherche. Autant dire invisible pour « {type_label} à {city} ».",
                    }
                )
            elif lead.dataforseo_organic_keywords < 10:
                args.append(
                    {
                        "key": "google_faible",
                        "weight": 65,
                        "label": "Très faible présence Google",
                        "hook": f"Seulement {lead.dataforseo_organic_keywords} mots-clés sur Google, "
                        f"pour un {type_label} en {city}, c'est très sous-exploité.",
                    }
                )

        # ── 4. 0 TRAFIC ORGANIQUE ──
        if (
            lead.dataforseo_organic_traffic is not None
            and lead.dataforseo_organic_traffic == 0
        ):
            args.append(
                {
                    "key": "zero_trafic",
                    "weight": 80,
                    "label": "Aucun trafic Google",
                    "hook": f"0 visiteur par mois depuis Google, tout le trafic passe à côté de {name}.",
                }
            )

        # ── 5. PAS MOBILE-FRIENDLY ──
        if lead.is_mobile_friendly is False:
            mobile_context = (
                "or beaucoup de visiteurs découvrent une activité depuis leur téléphone."
                if lead_type == "activite"
                else "or beaucoup de voyageurs comparent depuis leur téléphone."
            )
            args.append(
                {
                    "key": "pas_mobile",
                    "weight": 75,
                    "label": "Site non adapté mobile",
                    "hook": f"Le site de {name} ne s'affiche pas correctement sur téléphone, {mobile_context}",
                }
            )

        # ── 6. PAS DE RÉSERVATION DIRECTE ──
        if (
            lead_type
            in (
                "hotel",
                "camping",
                "gite",
                "chambre_hotes",
                "residence",
            )
            and lead.has_booking_system is False
        ):
            args.append(
                {
                    "key": "pas_resa_directe",
                    "weight": 70,
                    "label": "Pas de réservation directe",
                    "hook": "Aucun moteur de réservation sur le site, les visiteurs sont redirigés "
                    "vers des plateformes tierces, avec les commissions qui vont avec.",
                }
            )

        # ── 7. MAUVAIS SEO ──
        if lead.seo_score is not None and lead.seo_score < 40:
            args.append(
                {
                    "key": "mauvais_seo",
                    "weight": 65,
                    "label": "SEO très faible",
                    "hook": f"Score SEO de {lead.seo_score}/100, le site n'est pas construit pour "
                    f"être trouvé par les moteurs de recherche.",
                }
            )

        # ── 8. INVISIBLE POUR LES IA (GEO) ──
        if lead.geo_score is not None and lead.geo_score < 40:
            args.append(
                {
                    "key": "invisible_ia",
                    "weight": 55,
                    "label": "Invisible pour les moteurs IA",
                    "hook": f"Quand un voyageur demande à ChatGPT « {type_label} à {city} », "
                    f"{name} n'apparaît pas. La nouvelle recherche passe à côté de vous.",
                }
            )

        # ── 9. MAUVAIS AVIS GOOGLE ──
        if lead.google_rating is not None and lead.google_rating < 3.5:
            args.append(
                {
                    "key": "mauvais_avis",
                    "weight": 50,
                    "label": "Avis Google en difficulté",
                    "hook": f"Note Google de {lead.google_rating}/5, les voyageurs consultent "
                    f"les avis avant de réserver, c'est un frein visible.",
                }
            )

        # ── 10. SITE CASSÉ / INACCESSIBLE ──
        if lead.has_website is False and lead.website:
            args.append(
                {
                    "key": "site_casse",
                    "weight": 92,
                    "label": "Site web inaccessible",
                    "hook": f"L'URL de {name} existe mais le site est inaccessible - le parcours visiteur peut être bloqué.",
                }
            )

        # Trier par poids décroissant
        args.sort(key=lambda a: a["weight"], reverse=True)
        return args

    def _get_regional_context(self, lead: Lead) -> str:
        """Détermine le contexte touristique régional à partir du code postal."""
        return get_regional_context(lead)

    def _get_type_label(self, lead: Lead) -> str:
        """Retourne un label lisible pour le type d'établissement."""
        return get_type_label(lead)

    def _build_lead_context(self, lead: Lead) -> str:
        """Construit le contexte du lead pour l'IA."""
        type_label = self._get_type_label(lead)
        context_parts = [
            f"Nom de l'établissement: {lead.name}",
            f"Type: {type_label}",
            f"Ville: {lead.city or 'Non spécifiée'}",
        ]

        if lead.postal_code:
            context_parts.append(f"Code postal: {lead.postal_code}")

        if lead.region:
            context_parts.append(f"Région: {lead.region}")

        # Contexte touristique régional
        regional = self._get_regional_context(lead)
        if regional:
            context_parts.append(f"Contexte touristique local: {regional}")

        context_parts.append(f"Segment: {lead.priority_level}")

        if lead.star_rating:
            context_parts.append(f"Classement: {lead.star_rating}")

        # Avis Google
        if lead.google_rating is not None:
            context_parts.append(f"Note Google: {lead.google_rating}/5")
        if lead.google_reviews_count is not None:
            context_parts.append(f"Nombre d'avis Google: {lead.google_reviews_count}")

        # Infos site web
        if lead.website:
            context_parts.append(f"Site web: {lead.website}")

        if lead.website_quality_score is not None:
            context_parts.append(f"Qualité du site: {lead.website_quality_score}/100")

        if lead.seo_score is not None:
            context_parts.append(f"Score SEO: {lead.seo_score}/100")

        if lead.geo_score is not None:
            context_parts.append(f"Score GEO (optimisation IA): {lead.geo_score}/100")

        if lead.is_mobile_friendly is not None:
            context_parts.append(
                f"Mobile-friendly: {'Oui' if lead.is_mobile_friendly else 'Non'}"
            )

        checklist = getattr(lead, "website_review_checklist", None) or {}
        if isinstance(checklist, dict):
            checked_labels = {
                "site_officiel": "site officiel confirmé manuellement",
                "site_accessible": "site accessible",
                "reservation": "réservation détectée",
                "google_map": "carte / géolocalisation visible",
                "avis_clients": "avis clients visibles",
                "formulaire_contact": "formulaire de contact visible",
                "mobile": "affichage mobile correct",
                "photos": "photos ou galerie utiles",
                "horaires": "horaires visibles",
                "tarifs": "tarifs visibles",
            }
            checked = [
                label
                for key, label in checked_labels.items()
                if bool(checklist.get(key))
            ]
            if checked:
                context_parts.append("")
                context_parts.append("═══ VALIDATION MANUELLE SITE ═══")
                context_parts.extend([f"- {label}" for label in checked])
                context_parts.append(
                    "INSTRUCTION : ces points sont prouvés et peuvent être utilisés. "
                    "Ne pas inventer les points non cochés."
                )

        lead_type_val = lead.lead_type.value if lead.lead_type else "other"
        booking_relevant = lead_type_val in (
            "hotel",
            "camping",
            "gite",
            "chambre_hotes",
            "residence",
        )

        if booking_relevant and lead.has_booking_system is not None:
            if lead.has_booking_system:
                if lead.booking_platform:
                    context_parts.append(
                        f"Système de réservation: Oui, via {lead.booking_platform}"
                    )
                else:
                    context_parts.append(
                        "Système de réservation: Oui (intégré au site)"
                    )
            else:
                context_parts.append(
                    "Système de réservation en direct: NON, pas de moteur de réservation sur le site, le visiteur est redirigé vers une plateforme tierce"
                )
                if lead.booking_platform:
                    context_parts.append(
                        f"Plateforme tierce détectée (NE PAS nommer dans le message): {lead.booking_platform}"
                    )

        # Audit concret du site (constats réels à transformer en arguments)
        audit = lead.website_audit or {}
        findings = audit.get("findings") if isinstance(audit, dict) else None
        if findings:
            context_parts.append("")
            context_parts.append("═══ AUDIT CONCRET DU SITE (constats réels) ═══")
            for f in findings:
                context_parts.append(f"- {f}")
            context_parts.append(
                "INSTRUCTION : nommer 2 ou 3 de ces constats dans le message comme "
                "observations factuelles, puis montrer ce que Kawanah apporte en face "
                "(responsive et design moderne, formulaire de contact ou d'inscription, "
                "réservation directe seulement si elle est pertinente et détectée, "
                "avis clients mis en avant, carte d'accès, visibilité Google + IA)."
            )
            context_parts.append("")

        # Données DataForSEO, métriques Google réelles
        if lead.dataforseo_domain_rank is not None:
            context_parts.append(
                f"Autorité de domaine Google (DataForSEO): {lead.dataforseo_domain_rank}/100"
            )
        if lead.dataforseo_organic_keywords is not None:
            kw = lead.dataforseo_organic_keywords
            if kw == 0:
                context_parts.append(
                    "Mots-clés positionnés sur Google: 0 → site totalement invisible sur Google"
                )
            elif kw < 10:
                context_parts.append(
                    f"Mots-clés positionnés sur Google: {kw} (très faible présence organique)"
                )
            elif kw < 50:
                context_parts.append(
                    f"Mots-clés positionnés sur Google: {kw} (présence limitée)"
                )
            else:
                context_parts.append(f"Mots-clés positionnés sur Google: {kw}")
        if lead.dataforseo_organic_traffic is not None:
            traffic = lead.dataforseo_organic_traffic
            if traffic == 0:
                context_parts.append(
                    "Trafic organique mensuel (Google): 0 visiteur/mois → aucune visibilité naturelle"
                )
            else:
                context_parts.append(
                    f"Trafic organique mensuel estimé (Google): {traffic} visiteurs/mois"
                )

        if lead.established_date:
            from datetime import date as _d

            months = ((_d.today() - lead.established_date).days) / 30
            if months <= 18:
                context_parts.append(
                    f"Date de création (INSEE) : {lead.established_date.strftime('%B %Y')}, établissement récent ({int(months)} mois)"
                )
            else:
                context_parts.append(
                    f"Date de création (INSEE) : {lead.established_date.strftime('%Y')}"
                )

        if lead.room_count:
            context_parts.append(f"Nombre de chambres: {lead.room_count}")

        if lead.pitch_count:
            context_parts.append(f"Nombre d'emplacements: {lead.pitch_count}")

        if lead.capacity:
            context_parts.append(f"Capacité d'accueil: {lead.capacity} personnes")

        # Arguments forts détectés (triés par impact)
        strong_args = self._detect_strong_arguments(lead)
        if strong_args:
            context_parts.append("")
            context_parts.append("═══ ARGUMENTS FORTS (par ordre d'impact) ═══")
            for i, arg in enumerate(strong_args[:5], 1):
                context_parts.append(f"#{i} [{arg['label']}] : {arg['hook']}")
            context_parts.append("")
            context_parts.append(
                "INSTRUCTION CRITIQUE : Le message DOIT s'appuyer sur l'argument #1 "
                "comme angle principal. C'est le levier le plus fort pour ce prospect. "
                "Les autres arguments peuvent renforcer, mais l'attaque du message repose sur le #1."
            )

        return "\n".join(context_parts)

    def generate_message(
        self,
        lead: Lead,
        channel: MessageChannel = MessageChannel.EMAIL,
        tone: MessageTone = MessageTone.FRIENDLY,
        sender_name: str = "L'équipe Kawanah Tourisme",
        custom_instructions: Optional[str] = None,
    ) -> GeneratedMessage:
        """
        Génère un message personnalisé pour un lead.

        Args:
            lead: Le lead cible
            channel: Canal (email ou LinkedIn)
            tone: Ton du message
            sender_name: Nom de l'expéditeur
            custom_instructions: Instructions supplémentaires pour l'IA
        """
        website_match_status = getattr(
            lead, "website_match_status", WebsiteMatchStatus.UNKNOWN
        )
        if isinstance(website_match_status, str):
            try:
                website_match_status = WebsiteMatchStatus(website_match_status)
            except ValueError:
                website_match_status = WebsiteMatchStatus.UNKNOWN

        if lead.website and website_match_status != WebsiteMatchStatus.VERIFIED:
            return self._generate_unverified_site_message(
                lead, channel, tone, sender_name
            )

        if not self.client:
            # Mode démo sans API
            return self._generate_demo_message(
                lead, channel, tone, sender_name, custom_instructions
            )

        template = MessageTemplates.get_template(lead)
        lead_context = self._build_lead_context(lead)

        tone_nuance = {
            MessageTone.PROFESSIONAL: "Vouvoiement strict, registre soutenu.",
            MessageTone.FRIENDLY: "Vouvoiement mais ton accessible, naturel.",
            MessageTone.DIRECT: "Ultra direct, pas de fioritures.",
        }[tone]

        channel_format = {  # tone_nuance injecté dans le prompt ci-dessous
            MessageChannel.EMAIL: (
                "Format email.\n"
                "OBJET : 3 à 6 mots max. Factuel, jamais vendeur, jamais générique. "
                "Pas de majuscules partout, pas de !, pas d'emoji. "
                "Exemples selon segment, "
                "NOUVELLE STRUCTURE (ouverture récente) : 'félicitations pour votre ouverture' ou 'belle ouverture à [ville]'. Toujours positif, célébrer le lancement. "
                "SANS SITE : 'j'ai cherché [nom] en ligne' ou '[nom], introuvable sur Google'. "
                "MAUVAIS SEO : 'présence Google à vérifier' ou '[nom] sur Google'. "
                "GEO/IA : 'ce que ChatGPT dit de vous' ou 'ChatGPT connaît-il [nom] ?'. "
                "SITE CASSÉ : 'votre site, erreur ce matin'. "
                "PAS DE RÉSA DIRECTE : uniquement pour hébergements avec absence réellement détectée. "
                "Corps : 5-7 lignes max, paragraphes courts."
            ),
            MessageChannel.LINKEDIN: (
                "Format message LinkedIn. Pas d'objet. Corps : 4-5 lignes max, "
                "encore plus direct qu'un email."
            ),
        }[channel]

        seasonal = self._get_seasonal_context()

        prompt = f"""Tu es Laetitia, spécialiste web & référencement pour l'hospitalité chez Kawanah Tourisme.
Tu prospectes des établissements touristiques, loisirs et activités locales (hôtels, campings, gîtes, chambres d'hôtes, parcs, clubs, activités sportives).
Tu n'es pas commerciale - tu écris comme une experte qui partage une observation utile.
Chaque email suit une structure simple : observation concrète, lecture prudente, question ouverte.

{MessageTemplates.STYLE_RULES}

CONTEXTE DU PROSPECT :
{lead_context}

{MessageTemplates.OFFER_CONTEXT}

STRATÉGIE POUR CE SEGMENT :
{template}

CONTEXTE SAISONNIER (à glisser naturellement dans le message, sans le plaquer) :
En ce moment : {seasonal['hook']}.
Angle utile : {seasonal['angle']}.
Ne pas citer ces phrases mot pour mot. Les intégrer seulement si ça rend le message plus naturel.

FORMAT :
{channel_format}
Ton : {tone_nuance}
Contexte géographique : adapte naturellement au territoire ({self._get_regional_context(lead) or lead.city or 'France'}).
Vocabulaire : adapté au type, un camping a des emplacements pas des chambres, un gîte accueille des hôtes.
{f"INSTRUCTIONS MANUELLES PRIORITAIRES À INTÉGRER EXPLICITEMENT : {custom_instructions}" if custom_instructions else ""}

CTA : terminer par une question ouverte simple, puis OBLIGATOIREMENT, sur une nouvelle ligne juste avant la formule de politesse, la phrase EXACTE suivante (mot pour mot, sans la modifier) :
On peut prendre un rendez-vous pour en parler : {settings.booking_link}
Rythme : phrases courtes, pas de démonstration longue, pas de ton d'audit.

Génère le message au format exact suivant (rien d'autre) :
OBJET: [sujet bref et factuel]
---
[corps du message]

{sender_name}
Kawanah Tourisme
https://tourisme.kawanah.com/"""

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text
            return self._parse_response(content, lead, channel, tone)

        except Exception as e:
            logger.error(f"Erreur génération message: {e}")
            return self._generate_demo_message(
                lead, channel, tone, sender_name, custom_instructions
            )

    def _generate_unverified_site_message(
        self,
        lead: Lead,
        channel: MessageChannel,
        tone: MessageTone,
        sender_name: str = "Laetitia",
    ) -> GeneratedMessage:
        """Message sûr quand le site associé au lead n'est pas fiable."""
        name = lead.name
        city = lead.city or "votre secteur"
        signature = (
            f"{sender_name} pour Kawanah Tourisme\nhttps://tourisme.kawanah.com/"
        )
        booking_cta = (
            f"On peut prendre un rendez-vous pour en parler : {settings.booking_link}"
            if settings.booking_link
            else ""
        )

        body = f"""Bonjour,

En regardant {name} à {city}, je n'ai pas trouvé de site web propre suffisamment fiable à associer à votre activité.

Peut-être qu'il existe sous une autre adresse, ou que vous utilisez surtout d'autres canaux aujourd'hui. Dans tous les cas, c'est souvent un point qui complique la découverte pour les personnes qui cherchent rapidement des informations pratiques depuis leur téléphone.

Chez Kawanah, nous pouvons vous montrer à quoi ressemblerait une page claire pour présenter votre activité, votre localisation, vos informations de contact et les éléments qui rassurent les visiteurs.

{booking_cta}

Belle journée,

{signature}"""

        return GeneratedMessage(
            subject=f"{name} - présence en ligne",
            body=body,
            channel=channel,
            tone=tone,
            lead_segment=lead.priority_level,
            personalization_points=["site_non_valide", "nom_etablissement", "ville"],
        )

    def _parse_response(
        self, response: str, lead: Lead, channel: MessageChannel, tone: MessageTone
    ) -> GeneratedMessage:
        """Parse la réponse de l'IA."""
        # Extraire l'objet
        subject_match = re.search(r"OBJET:\s*(.+?)(?:\n|---)", response)
        subject = (
            subject_match.group(1).strip()
            if subject_match
            else "Votre présence en ligne"
        )

        # Extraire le corps
        body_match = re.search(r"---\s*(.+)", response, re.DOTALL)
        body = body_match.group(1).strip() if body_match else response

        # Identifier les points de personnalisation utilisés
        personalization = []
        if lead.name.lower() in body.lower():
            personalization.append("nom_etablissement")
        if lead.city and lead.city.lower() in body.lower():
            personalization.append("ville")
        if "seo" in body.lower():
            personalization.append("seo_score")
        if "geo" in body.lower() or "ia" in body.lower():
            personalization.append("geo_score")

        return GeneratedMessage(
            subject=subject,
            body=body,
            channel=channel,
            tone=tone,
            lead_segment=lead.priority_level,
            personalization_points=personalization,
        )

    def _compose_audit_message(
        self,
        lead: Lead,
        channel: MessageChannel,
        tone: MessageTone,
        name: str,
        type_label: str,
        visitors_word: str,
        booking_cta: str,
        signature: str,
        polite: str,
        audit: dict,
        findings: list,
    ) -> GeneratedMessage:
        """
        Message persuasif (AIDA en version douce) construit à partir de l'audit du site.
        On valorise l'établissement, on présente les manques comme un potentiel à révéler,
        jamais comme un défaut. USP : socle SEO & IA natif.
        """
        lead_type_val = lead.lead_type.value if lead.lead_type else "other"

        # Attention : compliment valorisant adapté au type
        compliment = {
            "activite": "propose une activité qui attire naturellement les familles et les groupes",
            "camping": "offre un cadre qui plaît aux familles comme aux amoureux du plein air",
            "hotel": "propose une expérience qui séduit voyageurs et clients de passage",
            "gite": "offre un accueil authentique qui marque les voyageurs",
            "chambre_hotes": "offre un accueil chaleureux qui fidélise les voyageurs",
        }.get(lead_type_val, "propose une expérience qui mérite d'être mise en valeur")

        # Intérêt : constats présentés en douceur (potentiel, jamais reproche)
        soft_frags: list[str] = []
        if not audit.get("is_mobile_friendly"):
            soft_frags.append("votre site n'est pas encore optimisé pour les mobiles")
        if audit.get("design_dated"):
            soft_frags.append("son design gagnerait à être rafraîchi")
        if (
            lead_type_val
            in (
                "hotel",
                "camping",
                "gite",
                "chambre_hotes",
                "residence",
            )
            and audit.get("has_reservation") is False
        ):
            soft_frags.append("la réservation en direct n'est pas encore possible")
        if audit.get("has_embedded_reviews") is False:
            soft_frags.append("les avis de vos clients ne sont pas mis en avant")
        if audit.get("has_map") is False:
            soft_frags.append("le plan d'accès n'est pas facile à repérer")
        if audit.get("has_contact_form") is False:
            soft_frags.append("il manque un formulaire de contact simple")

        soft_frags = soft_frags[:3]
        if len(soft_frags) > 1:
            constats_phrase = ", ".join(soft_frags[:-1]) + " et " + soft_frags[-1]
        elif soft_frags:
            constats_phrase = soft_frags[0]
        else:
            constats_phrase = "quelques détails gagneraient à être valorisés"

        if lead_type_val == "activite":
            visitor_goal = (
                "de comprendre où pratiquer, comment vous contacter ou s'inscrire, "
                "de trouver les horaires et les informations pratiques, et de découvrir "
                "la vie de votre structure dès la première visite"
            )
            conversion_goal = "transformer plus de visiteurs en demandes de contact"
        else:
            visitor_goal = (
                f"de réserver en quelques clics, de trouver tout de suite les informations pratiques, "
                f"de se rassurer avec les avis d'autres {visitors_word}, et de découvrir un univers moderne dès la première seconde"
            )
            conversion_goal = "transformer plus de visiteurs en clients"

        subject = (
            f"Votre {type_label} mérite un site à la hauteur de l'expérience proposée"
        )
        body = f"""Bonjour,

J'ai découvert votre site : {lead.website}

Votre {type_label} {compliment}, et ça se ressent. Aujourd'hui, votre présence en ligne ne reflète pas encore pleinement la qualité de l'expérience que vous offrez.

La plupart des visiteurs découvrent désormais un établissement depuis leur smartphone. Or {constats_phrase}.

Imaginez un site qui permette à vos visiteurs {visitor_goal}.

C'est exactement ce que nous concevons chez Kawanah : des sites modernes et responsives, avec un socle SEO et IA natif pour être visibles sur Google comme sur les nouveaux moteurs IA type ChatGPT. L'objectif est simple : {conversion_goal}.

Je peux vous montrer en 15 minutes ce à quoi pourrait ressembler une nouvelle version du site de {name}.

{booking_cta}

{polite}

{signature}"""

        return GeneratedMessage(
            subject=subject,
            body=body,
            channel=channel,
            tone=tone,
            lead_segment=lead.priority_level,
            personalization_points=[
                "nom_etablissement",
                "site_web",
                "audit_site",
                "type",
            ],
        )

    def _generate_demo_message(
        self,
        lead: Lead,
        channel: MessageChannel,
        tone: MessageTone,
        sender_name: str = "Laetitia",
        custom_instructions: Optional[str] = None,
    ) -> GeneratedMessage:
        """Génère un message de démo sans API, contextuellement pertinent."""
        priority = lead.priority_level
        name = lead.name
        city = lead.city or "votre région"
        if "kawanah" in sender_name.lower():
            signature = f"{sender_name}\nhttps://tourisme.kawanah.com/"
        else:
            signature = (
                f"{sender_name} pour Kawanah Tourisme\nhttps://tourisme.kawanah.com/"
            )
        website_reference = (
            f"J'ai regardé votre site : {lead.website}."
            if lead.website
            else "J'ai regardé votre site."
        )
        booking_cta = (
            f"On peut prendre un rendez-vous pour en parler : {settings.booking_link}"
            if settings.booking_link
            else ""
        )
        type_label = self._get_type_label(lead)

        # Adapter le vocabulaire au type d'établissement
        lead_type_val = lead.lead_type.value if lead.lead_type else "other"
        visitors_word = {
            "camping": "campeurs",
            "gite": "hôtes",
            "chambre_hotes": "hôtes",
            "activite": "clients",
        }.get(lead_type_val, "voyageurs")

        # Info étoiles si disponible
        star_info = ""
        if lead.star_rating:
            star_info = f" ({lead.star_rating})"

        # Détection nouvelle structure, date INSEE en priorité, proxy avis en fallback
        from datetime import date as _date

        is_new = False
        if lead.established_date:
            months_old = ((_date.today() - lead.established_date).days) / 30
            is_new = months_old <= 18
        else:
            reviews = lead.google_reviews_count or 0
            is_new = reviews < 15 and lead.has_website in (None, False)

        # Détection plateforme gîte (même logique que dans get_template)
        name_lower = name.lower()
        website_lower = (lead.website or "").lower()
        is_plateforme_gite = any(
            kw in name_lower or kw in website_lower
            for kw in [
                "gîte de france",
                "gites de france",
                "gîtes de france",
                "gites.fr",
                "clevacances",
                "clévacances",
            ]
        )
        # Identifier la plateforme pour la nommer dans le message
        if (
            "gîte de france" in name_lower
            or "gites de france" in name_lower
            or "gîtes de france" in name_lower
        ):
            plateforme_nom = "Gîtes de France"
        elif "gites.fr" in name_lower or "gites.fr" in website_lower:
            plateforme_nom = "gites.fr"
        elif "clevacances" in name_lower or "clévacances" in name_lower:
            plateforme_nom = "Clévacances"
        else:
            plateforme_nom = "la plateforme"

        # ── Arguments forts pour piloter le message ──────
        strong_args = self._detect_strong_arguments(lead)
        top_key = strong_args[0]["key"] if strong_args else None

        # ── Messages selon l'argument fort #1, voix Laetitia, diagnostic partagé ──────

        # Formule de politesse (rotation légère)
        polite = "Belle journée,"

        # ── Cas principal : site existant + audit concret → message vendeur ──────
        audit = lead.website_audit if isinstance(lead.website_audit, dict) else {}
        findings = audit.get("findings") or []
        # Fallback : leads analysés avant l'audit détaillé → dériver des constats des champs connus
        if not findings and lead.website:
            derived = []
            if lead.is_mobile_friendly is False:
                derived.append("le site n'est pas adapté au mobile (pas responsive)")
            if (
                lead.website_quality_score is not None
                and lead.website_quality_score < 45
            ):
                derived.append("le design est daté et manque de modernité")
            if lead.has_booking_system is False:
                derived.append("aucune réservation en direct sur le site")
            if lead.seo_score is not None and lead.seo_score < 40:
                derived.append("le site est peu visible sur Google")
            findings = derived
            if derived and not audit:
                audit = {
                    "is_mobile_friendly": lead.is_mobile_friendly,
                    "has_reservation": lead.has_booking_system,
                    "design_dated": (lead.website_quality_score or 100) < 45,
                    # Signaux non audités → considérés présents pour ne pas survendre
                    "has_contact_form": True,
                    "has_embedded_reviews": True,
                    "has_map": True,
                }
        if (
            lead.website
            and findings
            and not is_plateforme_gite
            and not custom_instructions
        ):
            return self._compose_audit_message(
                lead,
                channel,
                tone,
                name,
                type_label,
                visitors_word,
                booking_cta,
                signature,
                polite,
                audit,
                findings,
            )

        if custom_instructions:
            subject = f"{name} - mise en valeur en ligne"
            lead_type_val = lead.lead_type.value if lead.lead_type else "other"
            landing_angle = (
                "une page simple et claire"
                if "landing" in custom_instructions.lower()
                or "one page" in custom_instructions.lower()
                else "une page dédiée"
            )
            location_angle = (
                "avec une carte pour aider les visiteurs à vous situer immédiatement"
                if "carte" in custom_instructions.lower()
                or "géolocal" in custom_instructions.lower()
                or "geolocal" in custom_instructions.lower()
                else "avec un parcours plus lisible pour les visiteurs"
            )
            reviews_angle = (
                "et une meilleure intégration de vos avis clients"
                if "avis" in custom_instructions.lower()
                else "et une mise en valeur plus directe de l'expérience proposée"
            )
            if lead_type_val == "activite":
                conversion_line = (
                    "L'idée ne serait pas de tout refaire, plutôt de créer un point d'entrée plus lisible "
                    "pour aider les visiteurs à comprendre l'activité, trouver les informations pratiques "
                    "et vous contacter plus facilement."
                )
            else:
                conversion_line = (
                    "L'idée ne serait pas de tout refaire, plutôt de créer un point d'entrée plus lisible "
                    "pour améliorer la visibilité et faciliter le premier contact."
                )
            body = f"""Bonjour,

{website_reference}

Il y a peut-être une piste assez concrète : {landing_angle}, {location_angle}, {reviews_angle}.

{conversion_line}

Vous aviez déjà envisagé ce type de mise en valeur pour {name} ?

{booking_cta}

{polite}

{signature}"""
            return GeneratedMessage(
                subject=subject,
                body=body,
                channel=channel,
                tone=tone,
                lead_segment=priority,
                personalization_points=[
                    "instructions_manuelles",
                    "nom_etablissement",
                    "site_web",
                ],
            )

        if top_key == "site_wix_sans_domaine":
            subject = f"{name} - site"
            body = f"""Bonjour,

{website_reference}

On sent qu'il y a un vrai lieu derrière, avec de bons retours clients.

Le site pourrait peut-être passer un cap côté navigation, mise en valeur du lieu et réservation directe.

Vous aviez déjà prévu une mise à niveau technique du site ?

{booking_cta}

{polite}

{signature}"""

        elif is_plateforme_gite:
            subject = f"{name} et {plateforme_nom}"
            body = f"""Bonjour,

J'ai vu {name} via {plateforme_nom}.

C'est une bonne base, mais je me demandais si vous aviez aussi une présence à vous, en dehors de la plateforme.

Vous avez déjà prévu quelque chose dans ce sens, ou ce n'est pas le sujet pour le moment ?

{polite}

{signature}"""

        elif top_key in (
            "site_obsolete_critique",
            "site_obsolete",
            "site_vieillissant",
        ):
            # SITE OBSOLÈTE = argument massue, priorité absolue
            quality = lead.website_quality_score or 0

            # Construire les arguments secondaires à glisser
            secondary_notes = []
            for arg in strong_args[1:3]:
                if arg["key"] == "pas_resa_directe":
                    secondary_notes.append("pas de réservation en direct sur le site")
                elif arg["key"] == "mauvais_seo":
                    secondary_notes.append(f"SEO à {lead.seo_score}/100")
                elif arg["key"] == "pas_mobile":
                    secondary_notes.append("le site ne s'affiche pas bien sur mobile")
                elif arg["key"] in ("google_invisible", "google_faible"):
                    kw = lead.dataforseo_organic_keywords or 0
                    secondary_notes.append(
                        f"seulement {kw} mot{'s' if kw > 1 else ''}-clé{'s' if kw > 1 else ''} sur Google"
                    )
                elif arg["key"] == "invisible_ia":
                    secondary_notes.append("invisible pour ChatGPT et les moteurs IA")

            secondary_line = ""
            if secondary_notes:
                secondary_line = f"\n\nEn regardant de plus près : {', '.join(secondary_notes)}. Ce sont des points qui peuvent freiner le parcours visiteur."

            if quality < 25:
                subject = f"{name} - site"
                body = f"""Bonjour,

{website_reference}

Il y a sûrement une belle adresse derrière, mais en ligne l'image paraît un peu en retrait.{secondary_line}

Vous avez déjà une mise à jour prévue, ou ce n'est pas encore dans vos priorités ?

{polite}

{signature}"""
            else:
                subject = f"{name} - présence en ligne"
                body = f"""Bonjour,

{website_reference}

Le site fait le job, mais certains détails donnent l'impression qu'il pourrait être remis au niveau de ce que vous proposez aujourd'hui.{secondary_line}

Vous avez déjà prévu de le reprendre, ou ce n'est pas le moment ?

{polite}

{signature}"""

        elif is_new and "SANS SITE" in priority:
            if lead.established_date:
                opening_ref = f"en {lead.established_date.strftime('%B %Y')}"
            else:
                opening_ref = f"à {city}"

            subject = f"Félicitations pour {name}"
            body = f"""Bonjour,

Félicitations pour {name}{star_info} {opening_ref}.

Je regardais votre présence en ligne, justement parce que les premiers mois posent souvent les bases pour la suite.

Vous avez déjà prévu quelque chose côté site ou visibilité locale ?

{polite}

{signature}"""

        elif "SANS SITE" in priority:
            subject = f"{name} en ligne"
            body = f"""Bonjour,

En cherchant {name}{star_info}, je n'ai pas trouvé de site propre associé à l'établissement.

Peut-être que c'est volontaire, mais je voulais vous le signaler parce que l'information est moins directe à trouver.

Vous avez prévu d'en créer un, ou vous préférez rester sur les canaux actuels ?

{polite}

{signature}"""

        elif "VÉRIFIER" in priority:
            subject = f"{name} - accès au site"
            body = f"""Bonjour,

{website_reference}

Je suis tombée sur une erreur de chargement.

Je ne sais pas si c'est ponctuel, mais je préfère vous le signaler.

Vous l'aviez déjà vu de votre côté ?

{polite}

{signature}"""

        elif "CHAUD" in priority:
            if lead.dataforseo_organic_keywords == 0:
                subject = f"{name} sur Google"
                opening = (
                    f"J'ai regardé rapidement la présence Google de {name}{star_info}."
                )
                consequence = "Je n'ai pas vu de mot-clé positionné, donc il y a peut-être quelque chose à vérifier côté visibilité."
            elif (
                lead.dataforseo_organic_keywords is not None
                and lead.dataforseo_organic_keywords < 10
            ):
                subject = f"{name} sur Google"
                opening = f"J'ai regardé le référencement de {name}{star_info}."
                consequence = f"Il y a {lead.dataforseo_organic_keywords} mots-clés positionnés sur Google, ce qui laisse peut-être une marge à explorer."
            elif lead.dataforseo_organic_traffic == 0:
                subject = f"{name} - visibilité Google"
                opening = f"J'ai regardé le trafic de {name}{star_info}."
                consequence = "Je ne vois pas de trafic issu de Google en ce moment, donc je me demandais si ce point avait déjà été regardé."
            elif top_key == "pas_mobile":
                subject = f"{name} sur mobile"
                opening = (
                    f"J'ai ouvert votre site depuis mon téléphone : {lead.website}."
                    if lead.website
                    else f"J'ai ouvert le site de {name}{star_info} depuis mon téléphone."
                )
                consequence = "L'expérience m'a semblé un peu difficile, surtout pour lire vite ou aller plus loin."
            elif top_key == "pas_resa_directe":
                subject = f"{name} - vos réservations passent par un intermédiaire"
                opening = (
                    f"J'ai regardé le parcours de réservation sur votre site : {lead.website}."
                    if lead.website
                    else f"J'ai regardé le parcours de réservation sur le site de {name}{star_info}."
                )
                consequence = "J'ai l'impression qu'il passe par un intermédiaire, donc je me demandais si la réservation directe était un sujet chez vous."
            else:
                subject = f"{name} - votre présence en ligne"
                opening = (
                    f"J'ai regardé votre site : {lead.website}."
                    if lead.website
                    else f"J'ai regardé la présence en ligne de {name}{star_info}."
                )
                consequence = "Il y a quelques points qui mériteraient peut-être d'être clarifiés, selon vos priorités du moment."

            body = f"""Bonjour,

{opening}

{consequence}

Vous avez déjà prévu de regarder ça ?

{polite}

{signature}"""

        else:  # TIÈDE ou FROID
            if (
                lead.dataforseo_organic_keywords
                and lead.dataforseo_organic_keywords >= 50
            ):
                traffic_detail = (
                    f", environ {lead.dataforseo_organic_traffic} visiteurs/mois"
                    if lead.dataforseo_organic_traffic
                    else ""
                )
                opening = f"Le référencement Google de {name}{star_info} est solide - {lead.dataforseo_organic_keywords} mots-clés positionnés{traffic_detail}."
            elif (
                lead.dataforseo_organic_keywords
                and lead.dataforseo_organic_keywords > 0
            ):
                opening = f"J'ai regardé la présence Google de {name}{star_info} - {lead.dataforseo_organic_keywords} mots-clés positionnés, c'est honnête."
            else:
                opening = (
                    f"J'ai regardé votre site : {lead.website} - bien construit."
                    if lead.website
                    else f"J'ai regardé le site de {name}{star_info} - bien construit."
                )

            subject = f"{name} et les recherches IA"
            body = f"""Bonjour,

{opening}

Je me demandais si vous aviez déjà regardé ce que les moteurs IA répondent quand quelqu'un cherche un {type_label} à {city}.

J'ai fait un premier test pour {name}, je peux vous partager ce que j'ai vu si le sujet vous intéresse.

Au plaisir d'échanger,

{signature}"""

        return GeneratedMessage(
            subject=subject,
            body=body,
            channel=channel,
            tone=tone,
            lead_segment=priority,
            personalization_points=[
                "nom_etablissement",
                "ville",
                "type",
                "contexte_regional",
            ],
        )

    def generate_variations(
        self,
        lead: Lead,
        count: int = 3,
        channel: MessageChannel = MessageChannel.EMAIL,
    ) -> list[GeneratedMessage]:
        """Génère plusieurs variations d'un message pour A/B testing."""
        variations = []

        tones = [MessageTone.PROFESSIONAL, MessageTone.FRIENDLY, MessageTone.DIRECT]

        for i, tone in enumerate(tones[:count]):
            message = self.generate_message(lead, channel=channel, tone=tone)
            variations.append(message)

        return variations


# Fonction helper
def generate_message_for_lead(
    lead: Lead,
    channel: str = "email",
    tone: str = "friendly",
    sender_name: str = "L'équipe Kawanah Tourisme",
) -> dict:
    """Génère un message pour un lead (helper pour l'API)."""
    service = AIService()

    channel_enum = MessageChannel(channel)
    tone_enum = MessageTone(tone)

    message = service.generate_message(
        lead=lead,
        channel=channel_enum,
        tone=tone_enum,
        sender_name=sender_name,
    )

    return {
        "subject": message.subject,
        "body": message.body,
        "channel": message.channel.value,
        "tone": message.tone.value,
        "lead_segment": message.lead_segment,
        "personalization_points": message.personalization_points,
    }
