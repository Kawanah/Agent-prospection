"""
Définition des outils (Tools) pour l'agent de prospection.
Ces outils sont appelés par l'agent IA selon ses besoins.
"""

from typing import Optional, Union, Dict, List
from dataclasses import dataclass
from enum import Enum

# Définition des outils au format Claude Tool Use
AGENT_TOOLS = [
    {
        "name": "search_leads",
        "description": """Recherche des leads (établissements) dans la base de données selon des critères.
        Utilise cet outil pour trouver des prospects à contacter.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "segment": {
                    "type": "string",
                    "description": "Segment de leads à rechercher: 'sans_site', 'a_verifier', 'chaud', 'tiede', 'froid', ou 'all'",
                    "enum": [
                        "sans_site",
                        "a_verifier",
                        "chaud",
                        "tiede",
                        "froid",
                        "all",
                    ],
                },
                "city": {
                    "type": "string",
                    "description": "Filtrer par ville (optionnel)",
                },
                "lead_type": {
                    "type": "string",
                    "description": "Type d'établissement: 'hotel', 'camping', 'gite', 'chambre_hotes', 'residence', 'activite'",
                    "enum": [
                        "hotel",
                        "camping",
                        "gite",
                        "chambre_hotes",
                        "residence",
                        "activite",
                    ],
                },
                "status": {
                    "type": "string",
                    "description": "Statut du lead: 'new', 'enriched', 'contacted', etc.",
                    "enum": [
                        "new",
                        "enriched",
                        "contacted",
                        "responded",
                        "interested",
                        "not_interested",
                    ],
                },
                "limit": {
                    "type": "integer",
                    "description": "Nombre maximum de résultats (défaut: 10, max: 50)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_lead_details",
        "description": """Récupère les détails complets d'un lead spécifique par son ID.
        Utilise cet outil pour avoir toutes les informations avant de rédiger un message.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "integer",
                    "description": "L'identifiant unique du lead",
                }
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "analyze_lead_website",
        "description": """Analyse le site web d'un lead pour déterminer sa qualité, son SEO et son score GEO.
        Utilise cet outil pour enrichir un lead avec des données sur son site web actuel.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "integer",
                    "description": "L'identifiant du lead dont on veut analyser le site",
                }
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "analyze_google_reviews",
        "description": """Analyse les avis Google d'un établissement via l'API Google Places.
        Récupère : note moyenne, nombre d'avis, fréquence (avis par mois), tendance (croissance/déclin).
        Utilise cet outil pour évaluer la réputation et l'activité d'un établissement.
        IMPORTANT : Un établissement avec beaucoup d'avis récents et une tendance "growing" est un bon prospect.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "integer",
                    "description": "L'identifiant du lead dont on veut analyser les avis",
                },
                "force_refresh": {
                    "type": "boolean",
                    "description": "Si true, réanalyse même si déjà fait (défaut: false)",
                },
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "generate_message",
        "description": """Génère un message de prospection personnalisé pour un lead.
        Le message est adapté au segment du lead et au canal choisi.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "integer", "description": "L'identifiant du lead"},
                "channel": {
                    "type": "string",
                    "description": "Canal de communication: 'email' ou 'linkedin'",
                    "enum": ["email", "linkedin"],
                },
                "tone": {
                    "type": "string",
                    "description": "Ton du message: 'professional', 'friendly', 'direct'",
                    "enum": ["professional", "friendly", "direct"],
                },
                "custom_instructions": {
                    "type": "string",
                    "description": "Instructions personnalisées pour adapter le message (optionnel)",
                },
            },
            "required": ["lead_id", "channel"],
        },
    },
    {
        "name": "queue_email",
        "description": """Met un email en file d'attente pour envoi.
        L'email sera envoyé après validation humaine si configuré ainsi.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "integer",
                    "description": "L'identifiant du lead destinataire",
                },
                "subject": {"type": "string", "description": "Objet de l'email"},
                "body": {"type": "string", "description": "Corps de l'email"},
                "requires_approval": {
                    "type": "boolean",
                    "description": "Si true, attend une validation humaine avant envoi (défaut: true)",
                },
            },
            "required": ["lead_id", "subject", "body"],
        },
    },
    {
        "name": "update_lead_status",
        "description": """Met à jour le statut d'un lead dans le pipeline de prospection.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "integer", "description": "L'identifiant du lead"},
                "status": {
                    "type": "string",
                    "description": "Nouveau statut",
                    "enum": [
                        "new",
                        "enriched",
                        "contacted",
                        "responded",
                        "interested",
                        "not_interested",
                        "converted",
                        "invalid",
                    ],
                },
                "notes": {
                    "type": "string",
                    "description": "Notes sur la mise à jour (optionnel)",
                },
            },
            "required": ["lead_id", "status"],
        },
    },
    {
        "name": "get_campaign_stats",
        "description": """Récupère les statistiques de prospection: nombre de leads par segment,
        taux de réponse, emails en attente, etc.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Période des stats: 'today', 'week', 'month', 'all'",
                    "enum": ["today", "week", "month", "all"],
                }
            },
            "required": [],
        },
    },
    {
        "name": "verify_website",
        "description": """IMPORTANT: Utilise cet outil AVANT d'envoyer un email à un lead marqué 'SANS SITE'.
        Recherche sur le web si l'établissement a réellement un site web.
        Évite d'envoyer des emails embarrassants du type 'vous n'avez pas de site' alors qu'ils en ont un.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {
                    "type": "integer",
                    "description": "L'identifiant du lead à vérifier",
                },
                "establishment_name": {
                    "type": "string",
                    "description": "Nom de l'établissement (si pas de lead_id)",
                },
                "city": {
                    "type": "string",
                    "description": "Ville de l'établissement (optionnel, améliore la précision)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "request_human_decision",
        "description": """Demande une décision à l'humain pour une action importante.
        Utilise cet outil quand tu as besoin de validation avant de continuer.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "La question ou demande de décision",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Les options possibles (optionnel)",
                },
                "context": {
                    "type": "string",
                    "description": "Contexte supplémentaire pour aider la décision",
                },
            },
            "required": ["question"],
        },
    },
]


@dataclass
class ToolResult:
    """Résultat de l'exécution d'un outil."""

    success: bool
    data: Union[Dict, List, str, None]
    error: Optional[str] = None
    requires_human_action: bool = False


class AgentAction(str, Enum):
    """Actions que l'agent peut effectuer."""

    SEARCH = "search_leads"
    GET_DETAILS = "get_lead_details"
    ANALYZE = "analyze_lead_website"
    ANALYZE_REVIEWS = "analyze_google_reviews"
    VERIFY_WEBSITE = "verify_website"
    GENERATE_MESSAGE = "generate_message"
    QUEUE_EMAIL = "queue_email"
    UPDATE_STATUS = "update_lead_status"
    GET_STATS = "get_campaign_stats"
    ASK_HUMAN = "request_human_decision"
