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
from app.models.lead import Lead

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
    Stratégies de message par segment — méthode A.I.D.A.

    Voix : Laetitia, experte web hospitalité. Ton expert détendu, pair-à-pair.
    Structure : Attention → Intérêt → Désir → Action.
    Jamais de liste, jamais de pitch produit, 6-8 lignes max.
    """

    # ─── Règles de style globales injectées dans chaque prompt ────────────────
    STYLE_RULES = """
RÈGLES DE STYLE ABSOLUES (à respecter impérativement) :
- Tu écris comme Laetitia : experte web spécialisée hospitalité, ton détendu et direct, ni commercial ni corporate
- Structure AIDA obligatoire :
  A - ATTENTION : première ligne percutante, factuelle, qui parle de LUI (pas de toi)
  I - INTÉRÊT : développe pourquoi c'est un enjeu concret pour son établissement
  D - DÉSIR : fait entrevoir ce que ça changerait concrètement (sans pitcher de service)
  A - ACTION : question ouverte courte qui invite à répondre, + lien de rendez-vous en option légère
- TOUJOURS commencer le mail par "Bonjour," sur une ligne seule
- TOUJOURS terminer par une formule de politesse courte avant la signature (ex: "Belle journée,", "Au plaisir d'échanger,", "À bientôt,", "Bonne continuation,")
- JAMAIS de guillemets « » ou " " dans le message
- JAMAIS de tiret long — (em dash). Utiliser le tiret court - à la place
- JAMAIS de liste à puces ou tirets
- JAMAIS "Je me permets de vous contacter"
- JAMAIS de présentation de l'agence dans le corps du message (juste la signature)
- Maximum 7 lignes dans le corps du message (hors bonjour et signature)
- Le lecteur doit sentir que tu as regardé SA situation spécifiquement, pas qu'il reçoit un email en masse
- La partie DÉSIR ne cite jamais un service Kawanah — elle décrit un bénéfice concret (plus de réservations, meilleure visibilité, indépendance)
- La partie ACTION finit par une vraie question qui invite à répondre (pas "seriez-vous disponible pour un appel ?")
- Signature : Laetitia pour Kawanah Tourisme\ntravel.kawanah.com
"""

    SANS_SITE = """
SITUATION : L'établissement n'a pas de site web.

STRUCTURE AIDA à suivre :
A - ATTENTION : ouvrir avec le fait brut — "En cherchant [nom] en ligne, je ne trouve rien." Court, factuel, pas de drama.
I - INTÉRÊT : expliquer l'enjeu concret — les voyageurs qui cherchent un [type] à [ville] passent directement chez la concurrence qui apparaît en premier.
D - DÉSIR : faire entrevoir ce que ça change — un établissement visible en ligne capte ces réservations sans effort, même en dehors des plateformes. Mentionner naturellement que Google ET les moteurs IA (ChatGPT, Perplexity) indexent un site dès l'ouverture.
A - ACTION : demander si c'est un choix délibéré ou si c'est en projet — question ouverte qui qualifie sans forcer.
Ne pas pitcher. Laisser la curiosité faire le travail.
"""

    A_VERIFIER = """
SITUATION : Le site semble inaccessible ou cassé.

STRUCTURE AIDA à suivre :
A - ATTENTION : ouvrir avec le fait brut — "J'ai essayé d'accéder au site de [nom] ce matin — erreur." Court, factuel, comme une alerte entre pairs.
I - INTÉRÊT : l'enjeu concret — un voyageur qui tombe sur une erreur part en 3 secondes chez le concurrent d'à côté. Chaque jour que ça dure, c'est des réservations perdues.
D - DÉSIR : un site qui répond correctement, ça retient le visiteur et le convertit. Glisser que c'est souvent un problème technique simple à corriger.
A - ACTION : demander si c'est un problème connu de leur côté, ou si l'info est nouvelle pour eux.
Ton : entre pairs qui se rendent service, pas vendeur qui détecte une opportunité.
"""

    CHAUD = """
SITUATION : Le site existe mais la qualité est faible (SEO mauvais, design daté, pas mobile-friendly).

STRUCTURE AIDA à suivre :
A - ATTENTION : ouvrir avec le chiffre ou l'observation qui claque.
  Si données DataForSEO disponibles → "J'ai regardé la présence Google de [nom] : 0 mot-clé positionné. Invisible pour les recherches [type] à [ville]."
  Si pas de données → "J'ai visité le site de [nom] — pour être direct, il ne joue pas dans la même cour que vos concurrents."
I - INTÉRÊT : l'enjeu — les voyageurs comparent 3-4 sites avant de choisir. Un site qui date ou invisible Google, c'est une décision de réservation perdue à chaque recherche.
D - DÉSIR : ce que ça change — un site optimisé pour Google ET les moteurs IA (ChatGPT, Perplexity) capte ces recherches automatiquement, 24h/24, sans commission.
A - ACTION : "est-ce que c'est quelque chose que vous avez déjà eu le temps de regarder ?" Question légère, ouverte.
NE PAS lister les services Kawanah.
"""

    TIEDE_GEO = """
SITUATION : Le site est correct, le SEO Google est OK, mais la présence sur les moteurs IA est absente.

STRUCTURE AIDA à suivre :
A - ATTENTION : ouvrir par un compliment factuel — reconnaître la bonne présence Google (avec chiffres si dispo). "J'ai regardé [nom] sur Google — solide présence. Une chose m'a quand même interpellé..."
I - INTÉRÊT : le contraste SEO ✓ / IA ✗ — être bien référencé Google ne suffit plus. Les voyageurs demandent maintenant directement à ChatGPT ou Perplexity, qui donnent des recommandations basées sur d'autres critères.
D - DÉSIR : ce que ça change — un établissement optimisé pour les moteurs IA (données structurées, contenu riche) apparaît dans ces réponses générées. C'est un canal entier à aller chercher.
A - ACTION : "est-ce que vous avez regardé ce que ChatGPT répond quand on lui demande un [type] à [ville] ?" Proposer de partager le résultat de la requête.
Rester curieux, pas alarmiste. C'est une opportunité, pas un problème.
"""

    FROID_GEO = """
SITUATION : Le site est bon, le SEO est solide.

STRUCTURE AIDA à suivre :
A - ATTENTION : compliment factuel et sincère. Citer les chiffres DataForSEO si disponibles — "J'ai regardé [nom] : bon référencement Google, belle présence. Pas si courant dans le secteur."
I - INTÉRÊT : introduire la prochaine frontière naturellement — "une chose que j'ai vérifiée en parallèle : ce que ChatGPT répond quand on cherche un [type] à [ville]."
D - DÉSIR : ce que ça représente — les moteurs IA génèrent une nouvelle vague de voyageurs qui ne passent plus par Google. Un établissement déjà bien positionné peut capitaliser dessus avec quelques ajustements ciblés.
A - ACTION : proposer de partager le résultat de la requête IA qu'on a faite pour eux — ça matérialise la valeur sans pitcher. "Voulez-vous que je vous l'envoie ?"
Ton : expert curieux qui partage une découverte, pas commercial qui vend un service.
"""

    SITE_OBSOLETE = """
SITUATION : L'établissement a un site web, mais il est clairement obsolète / daté / amateur.

STRUCTURE AIDA à suivre :
A - ATTENTION : l'observation directe, factuelle et bienveillante — "J'ai visité le site de [nom] — pour être honnête, il ne reflète pas ce que vous proposez." Précis sur ce qui cloche : design d'une autre époque, pas aux standards actuels.
I - INTÉRÊT : l'enjeu concret — un voyageur compare 3-4 sites avant de réserver. Un site daté, c'est une réservation perdue au profit du concurrent qui a une belle image en ligne. Glisser des données techniques si disponibles (SEO, mobile) en renfort.
D - DÉSIR : ce que ça change — un site à l'image de l'établissement retient le visiteur, inspire confiance, et convertit. Mentionner que les sites modernes sont aussi indexés par les moteurs IA (ChatGPT, Perplexity) dès la mise en ligne.
A - ACTION : "est-ce que la refonte du site c'est quelque chose que vous avez en projet ?" Question ouverte, légère.
TON : direct mais bienveillant. On constate un décalage, on ne juge pas leur travail.
"""

    PLATEFORME_GITE = """
SITUATION : Établissement référencé sur une plateforme de gîtes (Gîtes de France, gites.fr, Clévacances...).

STRUCTURE AIDA à suivre :
A - ATTENTION : reconnaître la plateforme comme une vraie légitimité — "j'ai trouvé [nom] sur [plateforme] — beau label." Puis introduire l'observation : toutes les réservations passent par là, aucun trafic propre.
I - INTÉRÊT : l'enjeu concret — quand un voyageur demande à ChatGPT "gîte à [ville] pour 6 personnes", la plateforme n'apparaît pas dans ces réponses. Leur nom non plus. Toute la nouvelle génération de recherche passe à côté.
D - DÉSIR : ce que ça change — une présence propre, même simple, permet de capter des réservations directes ET d'être visible sur les moteurs IA. Complémentaire à la plateforme, pas concurrent.
A - ACTION : "est-ce que vous avez pensé à avoir une présence propre pour capter ces réservations hors plateforme ?"
TON : expert qui partage une observation factuelle. Pas de critique de la plateforme.
"""

    PAS_DE_RESA_DIRECTE = """
SITUATION : L'établissement a un site web, mais AUCUN système de réservation en direct. Le visiteur est redirigé vers une plateforme tierce.

RÈGLES IMPÉRATIVES :
- NE JAMAIS nommer la plateforme tierce (pas de "Booking", "Airbnb"). Dire "une plateforme tierce" ou "un intermédiaire".
- NE JAMAIS chiffrer en euros ou en pourcentage. Pas de "15-25%".
- NE JAMAIS être péjoratif. C'est une observation factuelle, pas un problème.

STRUCTURE AIDA à suivre :
A - ATTENTION : observation concrète — "J'ai visité le site de [nom], j'ai voulu réserver et j'ai été redirigé vers une plateforme tierce." Factuel, neutre.
I - INTÉRÊT : l'enjeu — les voyageurs qui arrivent sur un site préfèrent réserver directement dessus quand c'est possible. Chaque redirection vers une plateforme, c'est une réservation qui échappe au site.
D - DÉSIR : ce que ça change — réserver directement sur le site capte ces clients, permet de récupérer leurs données, et offre une visibilité propre sur Google ET les moteurs IA (ChatGPT, Perplexity). Deux canaux en plus, sans intermédiaire.
A - ACTION : "est-ce que la réservation directe c'est quelque chose que vous avez déjà envisagé ?"
TON : curieux, factuel, positif. On parle d'opportunité, pas de problème.
"""

    NOUVELLE_STRUCTURE = """
SITUATION : Établissement qui vient d'ouvrir (date de création INSEE récente, moins de 18 mois).

STRUCTURE AIDA à suivre :
A - ATTENTION : félicitations chaleureux et sincères — mentionner l'ouverture, la ville, le type. Montrer qu'on a regardé.
  "Félicitations pour l'ouverture de [nom] à [ville] — belle initiative dans un secteur qui en a besoin."
  Si date connue : "Je vois que vous avez ouvert en [mois] — félicitations, belle aventure qui commence."
I - INTÉRÊT : le contexte qui rend ça urgent — les établissements qui posent leur présence en ligne dès l'ouverture captent les premiers clients bien plus vite. Google et les moteurs IA indexent un nouveau site en quelques semaines — c'est une fenêtre courte.
D - DÉSIR : ce que ça change concrètement — être trouvé dès l'ouverture sur Google ET sur ChatGPT, Perplexity. Les voyageurs qui cherchent un [type] à [ville] tombent sur l'établissement avant même qu'il soit connu. Une seule phrase sur ce qu'on fait si nécessaire, pas de liste.
A - ACTION : demander où ils en sont sur leur présence en ligne — site en cours, projet, ou pas encore réfléchi ? Question légère, ouverte.
TON : énergique et bienveillant. On célèbre leur lancement, on n'arrive pas avec un problème.
JAMAIS de liste à puces. Maximum 8 lignes corps.
"""

    @classmethod
    def get_template(cls, lead: Lead) -> str:
        """
        Retourne le template approprié selon l'argument fort #1 du lead.

        Logique :
        1. Détecter les arguments forts (triés par impact)
        2. L'argument #1 dicte le template — c'est l'angle d'attaque du message
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

    # Mapping départements → contexte touristique local
    REGIONAL_CONTEXT = {
        # Côte d'Azur / Méditerranée
        "06": "Côte d'Azur, tourisme balnéaire, soleil, plages, luxe, croisières",
        "13": "Provence, calanques, tourisme culturel, gastronomie méditerranéenne",
        "83": "Var, plages, Saint-Tropez, tourisme balnéaire et viticole",
        "34": "Hérault, plages méditerranéennes, Canal du Midi, oenotourisme",
        "30": "Gard, Pont du Gard, Cévennes, Camargue",
        "11": "Aude, Carcassonne, cathares, vignobles",
        "66": "Pyrénées-Orientales, Collioure, côte Vermeille, montagne et mer",
        # Atlantique / Sud-Ouest
        "33": "Gironde, Bordeaux, vignobles, Bassin d'Arcachon, surf",
        "40": "Landes, surf, forêt, thermalisme, tourisme nature",
        "64": "Pays Basque, Béarn, montagne, surf, gastronomie basque",
        "17": "Charente-Maritime, La Rochelle, île de Ré, tourisme balnéaire",
        "85": "Vendée, Puy du Fou, côte atlantique, tourisme familial",
        "44": "Loire-Atlantique, Nantes, La Baule, tourisme urbain et balnéaire",
        "56": "Morbihan, Golfe du Morbihan, mégalithes, îles",
        "29": "Finistère, Bretagne sauvage, phares, pointe du Raz",
        "22": "Côtes-d'Armor, Côte de Granit Rose, tourisme nature",
        "35": "Ille-et-Vilaine, Saint-Malo, Mont-Saint-Michel",
        # Montagne
        "73": "Savoie, stations de ski, thermalisme, lacs alpins",
        "74": "Haute-Savoie, Chamonix, Annecy, ski et randonnée alpine",
        "38": "Isère, Grenoble, Vercors, ski et randonnée",
        "05": "Hautes-Alpes, Serre Chevalier, Briançon, sports outdoor",
        "04": "Alpes-de-Haute-Provence, Gorges du Verdon, lavande",
        "65": "Hautes-Pyrénées, Lourdes, Pic du Midi, ski pyrénéen",
        "09": "Ariège, grottes, préhistoire, montagne pyrénéenne",
        "63": "Puy-de-Dôme, volcans d'Auvergne, thermalisme",
        "15": "Cantal, Salers, volcans, tourisme vert",
        # Paris / Île-de-France
        "75": "Paris, tourisme urbain, monuments, shopping, gastronomie",
        "77": "Seine-et-Marne, Disneyland Paris, Fontainebleau",
        "78": "Yvelines, Versailles, tourisme culturel",
        # Normandie
        "14": "Calvados, plages du débarquement, Deauville, fromages",
        "50": "Manche, Mont-Saint-Michel, Cherbourg, cotentin",
        "76": "Seine-Maritime, Étretat, Rouen, falaises",
        # Loire / Centre
        "37": "Indre-et-Loire, Châteaux de la Loire, gastronomie, vignobles",
        "41": "Loir-et-Cher, Chambord, châteaux, Sologne",
        "45": "Loiret, Orléans, forêt d'Orléans",
        # Corse
        "2A": "Corse-du-Sud, Ajaccio, Bonifacio, plages paradisiaques",
        "2B": "Haute-Corse, Bastia, Calvi, maquis, montagnes",
        "20": "Corse, île de beauté, plages, maquis, montagnes",
        # Outre-mer
        "971": "Guadeloupe, Caraïbes, plages tropicales",
        "972": "Martinique, Caraïbes, plages tropicales",
        "973": "Guyane, Amazonie, tourisme d'aventure",
        "974": "La Réunion, volcans, randonnée tropicale",
    }

    @staticmethod
    def _get_seasonal_context() -> dict:
        """Retourne le contexte saisonnier du mois courant pour personnaliser les messages."""
        from datetime import date

        month = date.today().month

        contexts = {
            1: {
                "hook": "les voyageurs planifient déjà leurs vacances d'été — les réservations anticipées commencent",
                "urgency": "C'est souvent en janvier que les décisions se prennent pour la saison.",
                "angle": "période creuse = moment idéal pour travailler sa visibilité avant la reprise",
            },
            2: {
                "hook": "les vacances d'hiver battent leur plein et les premières réservations de printemps arrivent",
                "urgency": "Les voyageurs qui cherchent pour mars-avril comparent les offres maintenant.",
                "angle": "fenêtre courte avant la reprise printanière",
            },
            3: {
                "hook": "la saison approche — les premières recherches pour mai et l'été s'accélèrent",
                "urgency": "Les établissements qui apparaissent bien en ligne maintenant captent ces réservations anticipées.",
                "angle": "dernier moment pour se préparer avant l'ouverture de saison",
            },
            4: {
                "hook": "les beaux jours arrivent, les ponts de mai approchent et les premières réservations d'été sont en cours",
                "urgency": "Beaucoup de voyageurs cherchent leurs destinations de mai et de l'été en ce moment même.",
                "angle": "les ponts de mai (1er, 8 mai, Ascension) génèrent un pic de recherches dès maintenant",
            },
            5: {
                "hook": "les ponts de mai et le début de saison estivale — les réservations de juillet-août sont en plein boom",
                "urgency": "C'est maintenant que les voyageurs réservent pour l'été.",
                "angle": "début de haute saison, chaque semaine compte",
            },
            6: {
                "hook": "l'été est là, les recherches de dernière minute s'intensifient",
                "urgency": "Les voyageurs qui n'ont pas encore réservé cherchent des disponibilités en temps réel.",
                "angle": "dernière fenêtre pour capter les réservations estivales",
            },
            7: {
                "hook": "pleine saison — le pic de fréquentation bat son plein",
                "urgency": "Peu de temps pour changer les choses maintenant, mais c'est le bon moment pour préparer la prochaine saison.",
                "angle": "anticiper l'après-saison et la rentrée",
            },
            8: {
                "hook": "pic estival — et déjà les premières recherches pour septembre et l'automne",
                "urgency": "Les early-adopters planifient leur automne maintenant.",
                "angle": "préparer la fin de saison et l'automne",
            },
            9: {
                "hook": "la rentrée arrive, et avec elle les premières recherches pour la Toussaint et les vacances d'automne",
                "urgency": "C'est le bon moment pour faire le bilan de saison et se préparer pour l'année prochaine.",
                "angle": "rentrée = moment idéal pour investir dans sa présence en ligne avant la prochaine saison",
            },
            10: {
                "hook": "les vacances de la Toussaint approchent et les premières réservations de Noël commencent",
                "urgency": "Les familles planifient leurs fêtes et séjours d'hiver maintenant.",
                "angle": "fenêtre entre deux saisons — moment idéal pour travailler le fond",
            },
            11: {
                "hook": "les fêtes de fin d'année approchent — réveillons, marchés de Noël, séjours hivernaux",
                "urgency": "Les réservations de décembre et janvier sont en cours.",
                "angle": "anticiper la nouvelle année et la prochaine saison",
            },
            12: {
                "hook": "fin d'année — et les bonnes résolutions pour la saison prochaine se prennent maintenant",
                "urgency": "C'est en décembre que les professionnels investissent dans ce qui va changer leur saison à venir.",
                "angle": "nouvelle année = nouvelle visibilité, c'est le moment d'agir",
            },
        }
        return contexts.get(month, contexts[4])

    @staticmethod
    def _detect_strong_arguments(lead: Lead) -> list[dict]:
        """
        Analyse un lead et retourne ses arguments forts, triés par impact.
        Chaque argument : { "key": str, "weight": int, "label": str, "hook": str }
        - label : nom court de l'argument
        - hook : phrase d'accroche percutante à utiliser dans le message
        """
        args = []
        type_label = {
            "hotel": "hôtel",
            "camping": "camping",
            "gite": "gîte",
            "chambre_hotes": "chambre d'hôtes",
            "residence": "résidence",
            "activite": "prestataire d'activités",
            "other": "établissement",
        }.get(lead.lead_type.value if lead.lead_type else "other", "établissement")
        city = lead.city or "votre ville"
        name = lead.name

        # ── 1. SITE OBSOLÈTE (quality < 40, site existant) ──
        if lead.has_website is True and lead.website_quality_score is not None:
            if lead.website_quality_score < 25:
                args.append(
                    {
                        "key": "site_obsolete_critique",
                        "weight": 95,
                        "label": "Site complètement obsolète",
                        "hook": f"Le site de {name} a besoin d'une refonte complète — design daté, "
                        f"pas aux standards actuels. Un voyageur qui arrive dessus repart immédiatement.",
                    }
                )
            elif lead.website_quality_score < 40:
                args.append(
                    {
                        "key": "site_obsolete",
                        "weight": 90,
                        "label": "Site obsolète",
                        "hook": f"Le site de {name} accuse son âge — il ne reflète pas la qualité "
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
                    "hook": f"Impossible de trouver {name} en ligne — les voyageurs qui cherchent "
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
                        "hook": f"0 mot-clé positionné sur Google — {name} n'existe pas dans les résultats "
                        f"de recherche. Autant dire invisible pour « {type_label} à {city} ».",
                    }
                )
            elif lead.dataforseo_organic_keywords < 10:
                args.append(
                    {
                        "key": "google_faible",
                        "weight": 65,
                        "label": "Très faible présence Google",
                        "hook": f"Seulement {lead.dataforseo_organic_keywords} mots-clés sur Google — "
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
                    "hook": f"0 visiteur par mois depuis Google — tout le trafic passe à côté de {name}.",
                }
            )

        # ── 5. PAS MOBILE-FRIENDLY ──
        if lead.is_mobile_friendly is False:
            args.append(
                {
                    "key": "pas_mobile",
                    "weight": 75,
                    "label": "Site non adapté mobile",
                    "hook": f"Le site de {name} ne s'affiche pas correctement sur téléphone — "
                    f"or +60% des recherches hôtelières se font sur mobile.",
                }
            )

        # ── 6. PAS DE RÉSERVATION DIRECTE ──
        if lead.has_booking_system is False:
            args.append(
                {
                    "key": "pas_resa_directe",
                    "weight": 70,
                    "label": "Pas de réservation directe",
                    "hook": f"Aucun moteur de réservation sur le site — les visiteurs sont redirigés "
                    f"vers des plateformes tierces, avec les commissions qui vont avec.",
                }
            )

        # ── 7. MAUVAIS SEO ──
        if lead.seo_score is not None and lead.seo_score < 40:
            args.append(
                {
                    "key": "mauvais_seo",
                    "weight": 65,
                    "label": "SEO très faible",
                    "hook": f"Score SEO de {lead.seo_score}/100 — le site n'est pas construit pour "
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
                    "hook": f"Note Google de {lead.google_rating}/5 — les voyageurs consultent "
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
                    "hook": f"L'URL de {name} existe mais le site est inaccessible — un voyageur "
                    f"qui tombe sur une page d'erreur repart en 3 secondes.",
                }
            )

        # Trier par poids décroissant
        args.sort(key=lambda a: a["weight"], reverse=True)
        return args

    def _get_regional_context(self, lead: Lead) -> str:
        """Détermine le contexte touristique régional à partir du code postal."""
        if lead.postal_code and len(lead.postal_code) >= 2:
            dept = lead.postal_code[:2]
            # Corse
            if lead.postal_code.startswith("20"):
                dept = "20"
            # Outre-mer
            if lead.postal_code.startswith("97") and len(lead.postal_code) >= 3:
                dept = lead.postal_code[:3]
            ctx = self.REGIONAL_CONTEXT.get(dept)
            if ctx:
                return ctx

        # Fallback sur le nom de ville pour les cas évidents
        city = (lead.city or "").lower()
        city_context = {
            "nice": "Côte d'Azur, tourisme balnéaire, soleil, plages, luxe",
            "cannes": "Côte d'Azur, festivals, plages, luxe, croisettes",
            "marseille": "Provence, calanques, tourisme culturel, port méditerranéen",
            "paris": "Tourisme urbain, monuments, shopping, gastronomie",
            "lyon": "Gastronomie, patrimoine UNESCO, tourisme urbain",
            "bordeaux": "Vignobles, gastronomie, architecture, fleuve",
            "biarritz": "Surf, Pays Basque, plages, thalasso",
            "chamonix": "Montagne, ski, alpinisme, Mont-Blanc",
            "annecy": "Lac, montagnes, vieille ville, sports nautiques",
            "strasbourg": "Alsace, marché de Noël, patrimoine, gastronomie",
            "ajaccio": "Corse, plages, Napoléon, maquis",
            "bastia": "Corse, port, Cap Corse",
            "lourdes": "Pèlerinage, Pyrénées, thermalisme",
            "saint-malo": "Côte d'Émeraude, corsaires, remparts, plages",
            "la rochelle": "Port, îles, tourisme balnéaire atlantique",
            "arcachon": "Bassin, dune du Pilat, huîtres, plages",
        }
        for city_name, ctx in city_context.items():
            if city_name in city:
                return ctx

        if lead.region:
            return f"Région {lead.region}"

        return ""

    def _get_type_label(self, lead: Lead) -> str:
        """Retourne un label lisible pour le type d'établissement."""
        labels = {
            "hotel": "hôtel",
            "camping": "camping",
            "gite": "gîte",
            "chambre_hotes": "chambre d'hôtes",
            "residence": "résidence de tourisme",
            "activite": "prestataire d'activités",
            "other": "établissement",
        }
        return labels.get(
            lead.lead_type.value if lead.lead_type else "other", "établissement"
        )

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

        if lead.has_booking_system is not None:
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
                    "Système de réservation en direct: NON — pas de moteur de réservation sur le site, le visiteur est redirigé vers une plateforme tierce"
                )
                if lead.booking_platform:
                    context_parts.append(
                        f"Plateforme tierce détectée (NE PAS nommer dans le message): {lead.booking_platform}"
                    )

        # Données DataForSEO — métriques Google réelles
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
                    f"Date de création (INSEE) : {lead.established_date.strftime('%B %Y')} — établissement récent ({int(months)} mois)"
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
                context_parts.append(f"#{i} [{arg['label']}] — {arg['hook']}")
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
        if not self.client:
            # Mode démo sans API
            return self._generate_demo_message(lead, channel, tone, sender_name)

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
                "Exemples selon segment — "
                "NOUVELLE STRUCTURE (ouverture récente) : 'félicitations pour votre ouverture' ou 'belle ouverture à [ville]'. Toujours positif, célébrer le lancement. "
                "SANS SITE : 'j'ai cherché [nom] en ligne' ou '[nom] — introuvable sur Google'. "
                "MAUVAIS SEO : '0 visiteur Google — [nom]' ou 'Google ne vous voit pas'. "
                "GEO/IA : 'ce que ChatGPT dit de vous' ou 'ChatGPT connaît-il [nom] ?'. "
                "SITE CASSÉ : 'votre site — erreur ce matin'. "
                "PAS DE RÉSA DIRECTE : 'vos réservations passent par Booking ?' ou 'réservation directe — [nom]'. "
                "Corps : 5-7 lignes max, paragraphes courts."
            ),
            MessageChannel.LINKEDIN: (
                "Format message LinkedIn. Pas d'objet. Corps : 4-5 lignes max, "
                "encore plus direct qu'un email."
            ),
        }[channel]

        booking_link = settings.booking_link
        seasonal = self._get_seasonal_context()

        prompt = f"""Tu es Laetitia, spécialiste web & référencement pour l'hospitalité chez Kawanah Tourisme.
Tu prospectes des établissements touristiques (hôtels, campings, gîtes, chambres d'hôtes).
Tu n'es pas commerciale — tu es experte. Ton approche : méthode A.I.D.A, pair-à-pair, détendu.
Chaque email suit la structure : Attention (accroche factuelle sur SA situation) → Intérêt (enjeu concret pour lui) → Désir (ce que ça changerait) → Action (question ouverte + lien rendez-vous).

{MessageTemplates.STYLE_RULES}

CONTEXTE DU PROSPECT :
{lead_context}

STRATÉGIE POUR CE SEGMENT :
{template}

CONTEXTE SAISONNIER (à glisser naturellement dans le message, sans le plaquer) :
En ce moment : {seasonal['hook']}.
Angle utile : {seasonal['angle']}.
Ne pas citer ces phrases mot pour mot — les intégrer naturellement dans l'accroche ou la conséquence.

FORMAT :
{channel_format}
Ton : {tone_nuance}
Contexte géographique : adapte naturellement au territoire ({self._get_regional_context(lead) or lead.city or 'France'}).
Vocabulaire : adapté au type — un camping a des emplacements pas des chambres, un gîte accueille des hôtes.
{f"Instructions complémentaires : {custom_instructions}" if custom_instructions else ""}

CTA : terminer par une question ouverte + proposer le lien de rendez-vous en option légère.
Format exact : "...ou si vous préférez qu'on en parle directement : {booking_link}"

Génère le message au format exact suivant (rien d'autre) :
OBJET: [sujet bref et factuel]
---
[corps du message]

{sender_name}
Kawanah Tourisme"""

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
            return self._generate_demo_message(lead, channel, tone, sender_name)

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

    def _generate_demo_message(
        self,
        lead: Lead,
        channel: MessageChannel,
        tone: MessageTone,
        sender_name: str = "Laetitia",
    ) -> GeneratedMessage:
        """Génère un message de démo sans API, contextuellement pertinent."""
        priority = lead.priority_level
        name = lead.name
        city = lead.city or "votre région"
        booking_link = settings.booking_link
        seasonal = self._get_seasonal_context()
        signature = f"{sender_name} pour Kawanah Tourisme\ntravel.kawanah.com"
        cta_link = f"ou si vous préférez qu'on en parle directement : {booking_link}"
        type_label = self._get_type_label(lead)

        # Contexte géographique pour personnaliser
        regional = self._get_regional_context(lead)
        # Phrase d'accroche locale adaptée
        if regional:
            # Extraire le premier mot-clé touristique pertinent
            keywords = [k.strip() for k in regional.split(",")]
            local_hook = keywords[0] if keywords else city
        else:
            local_hook = city

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

        # Détection nouvelle structure — date INSEE en priorité, proxy avis en fallback
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

        # ── Messages selon l'argument fort #1 — voix Laetitia, diagnostic partagé ──────

        # Formule de politesse (rotation légère)
        polite = "Belle journée,"

        if is_plateforme_gite:
            subject = f"{name} - visibilité hors {plateforme_nom}"
            body = f"""Bonjour,

{plateforme_nom}, c'est un label solide - ça rassure les voyageurs et ça légitime votre offre.

Ce que je remarque souvent, c'est que toute la visibilité passe par la plateforme. Aucun trafic direct vers {name}, aucune acquisition en propre. Et quand un voyageur demande à ChatGPT ou Perplexity un {type_label} à {city}, {plateforme_nom} n'apparaît pas, et votre nom non plus.

Vous avez déjà pensé à avoir un site en propre, pour capter des réservations directes et exister au-delà de {plateforme_nom} ? Répondez-moi ici, {cta_link}

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
                secondary_line = f"\n\nEn regardant de plus près : {', '.join(secondary_notes)}. Autant de réservations qui passent à côté."

            if quality < 25:
                subject = f"{name} - votre site a besoin d'une refonte"
                body = f"""Bonjour,

J'ai visité le site de {name}{star_info} - pour être honnête, il ne reflète pas du tout ce que vous proposez. Design d'une autre époque, pas aux standards actuels.

Un {visitors_word} qui cherche un {type_label} à {city} compare 3-4 sites avant de réserver. Avec un site comme ça, il passe au suivant.{secondary_line}

Est-ce que la refonte du site c'est quelque chose que vous avez en projet ? En ce moment {seasonal['hook']} - répondez-moi ici, {cta_link}

{polite}

{signature}"""
            else:
                subject = f"{name} - votre site commence à dater"
                body = f"""Bonjour,

J'ai visité le site de {name}{star_info} - il fait le job, mais face à la concurrence à {city}, il accuse son âge. La première impression en ligne, c'est souvent ce qui fait la différence entre une réservation et un rebond.{secondary_line}

C'est quelque chose que vous avez eu le temps de regarder ? En ce moment {seasonal['hook']} - répondez-moi ici, {cta_link}

{polite}

{signature}"""

        elif is_new and "SANS SITE" in priority:
            if lead.established_date:
                from datetime import date as _d

                months = int(((_d.today() - lead.established_date).days) / 30)
                opening_ref = f"en {lead.established_date.strftime('%B %Y')}"
                age_note = f"- {months} mois déjà" if months > 3 else "- tout frais"
            else:
                opening_ref = f"à {city}"
                age_note = ""

            subject = f"Félicitations pour l'ouverture {opening_ref}"
            body = f"""Bonjour,

Félicitations pour l'ouverture de {name}{star_info} {opening_ref} {age_note} - belle aventure qui commence.

Les établissements qui posent leur présence en ligne dès les premiers mois captent leurs premiers clients bien plus vite. Google et ChatGPT indexent un site bien structuré en quelques semaines - c'est une fenêtre courte à saisir au départ.

Vous avez déjà quelque chose en cours côté site, ou c'est encore en liste d'attente ? Répondez-moi ici, {cta_link}

{polite}

{signature}"""

        elif "SANS SITE" in priority:
            subject = f"j'ai cherché {name} en ligne"
            body = f"""Bonjour,

En cherchant un {type_label} à {city}, impossible de trouver de site pour {name}{star_info}.

Les {visitors_word} qui passent par là font pareil - ils passent leur chemin, pas par manque d'intérêt, juste parce qu'il n'y a rien à trouver.

C'est un choix délibéré ou c'est en projet ? En ce moment {seasonal['hook']} - répondez-moi ici, {cta_link}

{polite}

{signature}"""

        elif "VÉRIFIER" in priority:
            subject = f"{name} - erreur sur votre site"
            body = f"""Bonjour,

J'ai essayé d'accéder au site de {name}{star_info} ce matin - j'ai eu une erreur de chargement.

Un voyageur qui tombe là-dessus repart en 3 secondes, c'est mécanique.

Vous étiez au courant ? Répondez-moi ici, {cta_link}

{polite}

{signature}"""

        elif "CHAUD" in priority:
            if lead.dataforseo_organic_keywords == 0:
                subject = f"Google ne voit pas {name}"
                opening = f"J'ai regardé la présence Google de {name}{star_info} - 0 mot-clé positionné."
                consequence = f"Concrètement, quand quelqu'un cherche un {type_label} à {city}, vous n'existez pas dans les résultats."
            elif (
                lead.dataforseo_organic_keywords is not None
                and lead.dataforseo_organic_keywords < 10
            ):
                subject = (
                    f"{lead.dataforseo_organic_keywords} mots-clés Google - {name}"
                )
                opening = f"J'ai regardé le référencement de {name}{star_info} - {lead.dataforseo_organic_keywords} mots-clés positionnés sur Google."
                consequence = f"Pour un {type_label} en {local_hook}, c'est vraiment sous-exploité."
            elif lead.dataforseo_organic_traffic == 0:
                subject = f"0 visiteur Google - {name}"
                opening = f"J'ai regardé le trafic de {name}{star_info} - aucun visiteur issu de Google en ce moment."
                consequence = f"Pour des {visitors_word} qui cherchent en {local_hook}, c'est beaucoup de réservations perdues."
            elif top_key == "pas_mobile":
                subject = f"{name} - invisible sur mobile"
                opening = f"J'ai visité le site de {name}{star_info} depuis mon téléphone - l'expérience est compliquée."
                consequence = f"Plus de 60% des {visitors_word} cherchent depuis leur mobile. Un site qui ne s'affiche pas bien, c'est autant de réservations perdues."
            elif top_key == "pas_resa_directe":
                subject = f"{name} - vos réservations passent par un intermédiaire"
                opening = f"J'ai voulu réserver sur le site de {name}{star_info} - pas de moteur de réservation, je suis redirigé vers une plateforme tierce."
                consequence = f"Un moteur de réservation intégré = plus de réservations directes, moins de commissions."
            else:
                subject = f"{name} - votre présence en ligne"
                opening = f"J'ai regardé la présence en ligne de {name}{star_info} - il y a du potentiel inexploité."
                consequence = f"En ce moment les {visitors_word} cherchent activement en {local_hook}, c'est le bon moment pour se démarquer."

            body = f"""Bonjour,

{opening}

{consequence}

C'est quelque chose que vous avez eu le temps de regarder ? En ce moment {seasonal['hook']} - répondez-moi ici, {cta_link}

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
                opening = f"J'ai regardé le site de {name}{star_info} - bien construit."

            subject = f"ChatGPT connaît-il {name} ?"
            body = f"""Bonjour,

{opening}

Une question : est-ce que vous savez ce que ChatGPT répond quand quelqu'un lui demande le meilleur {type_label} à {city} ?

J'ai fait le test pour {name} - je vous envoie le résultat si ça vous intéresse. Ou directement : {cta_link}

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
