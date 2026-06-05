"""
Service Agent de Prospection - Le cerveau de l'agent autonome.
Utilise Claude avec Tool Use pour décider quelles actions effectuer.
"""

import json
from typing import Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from anthropic import Anthropic
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import get_settings
from app.models.lead import Lead, LeadStatus, LeadType
from app.agent.agent_tools import AGENT_TOOLS, ToolResult
from app.services.scoring_service import WebsiteAnalyzer, build_website_audit
from app.services.ai_service import AIService, MessageChannel, MessageTone
from app.services.web_verification_service import verify_establishment_website
from app.services.google_reviews_service import get_google_reviews_service
from app.services.email_service import send_prospection_email

settings = get_settings()


class AgentMode(str, Enum):
    """Mode de fonctionnement de l'agent."""

    AUTONOMOUS = "autonomous"  # Agit seul (avec limites)
    SUPERVISED = "supervised"  # Demande validation pour actions critiques
    MANUAL = "manual"  # Ne fait que suggérer, n'exécute pas


@dataclass
class AgentState:
    """État courant de l'agent."""

    mode: AgentMode = AgentMode.SUPERVISED
    conversation_history: list = field(default_factory=list)
    pending_actions: list = field(default_factory=list)
    completed_actions: list = field(default_factory=list)
    requires_human_input: bool = False
    human_question: Optional[str] = None
    session_started: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentMessage:
    """Message dans la conversation avec l'agent."""

    role: str  # "user", "assistant", "system"
    content: str
    tool_calls: Optional[list] = None
    tool_results: Optional[list] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ProspectionAgent:
    """
    Agent de prospection autonome utilisant Claude avec Tool Use.

    L'agent peut:
    - Rechercher des leads selon des critères
    - Analyser leurs sites web
    - Générer des messages personnalisés
    - Mettre des emails en file d'attente
    - Demander des décisions humaines quand nécessaire
    """

    SYSTEM_PROMPT = """Tu es un agent de prospection commercial expert pour Kawanah Tourisme,
une agence web spécialisée dans le secteur de l'hospitalité (hôtels, campings, gîtes).

TON OBJECTIF: Aider à identifier et contacter des prospects qui ont besoin de services web.

OFFRE TITAH:
- Sites internet avec socle SEO & IA natif
- Landing pages optimisées
- SEO (référencement Google)
- GEO (optimisation pour les moteurs IA comme ChatGPT, Perplexity)

SEGMENTS DE LEADS:
- 🔥 SANS SITE: Pas de site web → proposer création
- ⚠️ À VÉRIFIER: Site inaccessible → vérifier et proposer aide
- 🔥 CHAUD: Site de mauvaise qualité → proposer refonte
- 😐 TIÈDE: Site correct mais mal optimisé → proposer SEO/GEO
- ❄️ FROID: Bon site → proposer amélioration GEO

COMPORTEMENT:
- Tu es en mode SUPERVISÉ: tu demandes validation avant d'envoyer des emails
- Analyse bien le contexte du lead avant de générer un message
- Personnalise toujours les messages avec le nom et la ville
- Privilégie les leads SANS SITE et CHAUD (meilleurs prospects)
- Si tu as un doute, utilise l'outil request_human_decision

Tu as accès à des outils pour rechercher, analyser et contacter les leads.
Utilise-les de manière intelligente pour accomplir ta mission."""

    def __init__(self, db: AsyncSession, mode: AgentMode = AgentMode.SUPERVISED):
        self.db = db
        self.state = AgentState(mode=mode)
        self.client = None

        if settings.anthropic_api_key and settings.anthropic_api_key != "sk-ant-xxxxx":
            self.client = Anthropic(api_key=settings.anthropic_api_key)

        self.website_analyzer = WebsiteAnalyzer()
        self.ai_service = AIService()

    async def process_message(
        self, user_message: str
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Traite un message utilisateur et génère une réponse.
        Utilise un flux asynchrone pour renvoyer les messages au fur et à mesure.
        """
        # Ajouter le message utilisateur à l'historique
        self.state.conversation_history.append(
            {"role": "user", "content": user_message}
        )

        if not self.client:
            # Mode démo sans API — signaler clairement à l'utilisateur
            yield AgentMessage(
                role="system",
                content="⚠️ Mode démo actif — Clé API Claude non configurée. Les données affichées proviennent de la base locale, sans IA.",
            )
            yield AgentMessage(
                role="assistant", content=await self._demo_response(user_message)
            )
            return

        # Boucle d'agent: continuer tant que l'agent veut utiliser des outils
        while True:
            # Appeler Claude avec les outils
            try:
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=4096,
                    system=self.SYSTEM_PROMPT,
                    tools=AGENT_TOOLS,
                    messages=self.state.conversation_history,
                )
            except Exception as api_error:
                # En cas d'erreur API (crédits insuffisants, etc.), basculer en mode démo
                logger.warning(f"Erreur API Claude, passage en mode démo: {api_error}")
                yield AgentMessage(
                    role="assistant",
                    content=f"⚠️ *Erreur API Claude - Mode démo activé*\n\n{await self._demo_response(user_message)}",
                )
                return

            # Analyser la réponse
            assistant_content = []
            tool_calls = []
            text_response = ""

            for block in response.content:
                if block.type == "text":
                    text_response += block.text
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    tool_calls.append(
                        {"id": block.id, "name": block.name, "input": block.input}
                    )
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

            # Ajouter la réponse de l'assistant à l'historique
            self.state.conversation_history.append(
                {"role": "assistant", "content": assistant_content}
            )

            # Si pas d'appel d'outil, on a fini
            if not tool_calls:
                yield AgentMessage(role="assistant", content=text_response)
                break

            # Exécuter les outils et renvoyer les résultats
            tool_results = []
            for tool_call in tool_calls:
                logger.info(f"Agent appelle l'outil: {tool_call['name']}")

                # Exécuter l'outil
                result = await self._execute_tool(tool_call["name"], tool_call["input"])

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": json.dumps(
                            result.data if result.success else {"error": result.error},
                            ensure_ascii=False,
                        ),
                    }
                )

                # Yield le message de l'outil pour feedback temps réel
                yield AgentMessage(
                    role="system",
                    content=f"🔧 Outil `{tool_call['name']}` exécuté",
                    tool_calls=[tool_call],
                    tool_results=[result],
                )

                # Si l'outil nécessite une action humaine, arrêter
                if result.requires_human_action:
                    self.state.requires_human_input = True
                    self.state.human_question = (
                        result.data.get("question")
                        if isinstance(result.data, dict)
                        else None
                    )
                    yield AgentMessage(
                        role="assistant",
                        content=f"⏸️ **Action humaine requise**\n\n{self.state.human_question}",
                    )
                    return

            # Ajouter les résultats des outils à l'historique
            self.state.conversation_history.append(
                {"role": "user", "content": tool_results}
            )

            # Si stop_reason est "end_turn", on sort de la boucle
            if response.stop_reason == "end_turn":
                break

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> ToolResult:
        """Exécute un outil et retourne le résultat."""
        try:
            if tool_name == "search_leads":
                return await self._tool_search_leads(tool_input)

            elif tool_name == "get_lead_details":
                return await self._tool_get_lead_details(tool_input)

            elif tool_name == "analyze_lead_website":
                return await self._tool_analyze_website(tool_input)

            elif tool_name == "analyze_google_reviews":
                return await self._tool_analyze_google_reviews(tool_input)

            elif tool_name == "generate_message":
                return await self._tool_generate_message(tool_input)

            elif tool_name == "queue_email":
                return await self._tool_queue_email(tool_input)

            elif tool_name == "update_lead_status":
                return await self._tool_update_status(tool_input)

            elif tool_name == "get_campaign_stats":
                return await self._tool_get_stats(tool_input)

            elif tool_name == "verify_website":
                return await self._tool_verify_website(tool_input)

            elif tool_name == "request_human_decision":
                return await self._tool_request_human(tool_input)

            else:
                return ToolResult(
                    success=False, data=None, error=f"Outil inconnu: {tool_name}"
                )

        except Exception as e:
            logger.error(f"Erreur exécution outil {tool_name}: {e}")
            return ToolResult(success=False, data=None, error=str(e))

    # === IMPLÉMENTATION DES OUTILS ===

    async def _tool_search_leads(self, params: dict) -> ToolResult:
        """Recherche des leads selon critères."""
        query = select(Lead)

        # Filtres
        segment = params.get("segment")
        if segment and segment != "all":
            if segment == "sans_site":
                # Leads sans site valide
                query = query.where(Lead.website.is_(None) | (Lead.website == "-"))
            elif segment == "a_verifier":
                query = query.where(
                    Lead.website.isnot(None),
                    Lead.has_website == False,
                    Lead.website_quality_score.is_(None),
                )
            elif segment == "chaud":
                query = query.where(Lead.score >= 80)
            elif segment == "tiede":
                query = query.where(Lead.score >= 50, Lead.score < 80)
            elif segment == "froid":
                query = query.where(Lead.score < 50)

        if params.get("city"):
            query = query.where(Lead.city.ilike(f"%{params['city']}%"))

        if params.get("lead_type"):
            query = query.where(Lead.lead_type == LeadType(params["lead_type"]))

        if params.get("status"):
            query = query.where(Lead.status == LeadStatus(params["status"]))

        limit = min(params.get("limit", 10), 50)
        query = query.order_by(Lead.score.desc()).limit(limit)

        result = await self.db.execute(query)
        leads = result.scalars().all()

        return ToolResult(
            success=True,
            data={
                "count": len(leads),
                "leads": [
                    {
                        "id": lead.id,
                        "name": lead.name,
                        "city": lead.city,
                        "type": lead.lead_type.value if lead.lead_type else None,
                        "score": lead.score,
                        "segment": lead.priority_level,
                        "status": lead.status.value,
                        "website": lead.website,
                    }
                    for lead in leads
                ],
            },
        )

    async def _tool_get_lead_details(self, params: dict) -> ToolResult:
        """Récupère les détails d'un lead."""
        lead_id = params.get("lead_id")

        result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()

        if not lead:
            return ToolResult(
                success=False, data=None, error=f"Lead {lead_id} non trouvé"
            )

        return ToolResult(
            success=True,
            data={
                "id": lead.id,
                "name": lead.name,
                "type": lead.lead_type.value if lead.lead_type else None,
                "city": lead.city,
                "region": lead.region,
                "website": lead.website,
                "email": lead.email,
                "phone": lead.phone,
                "score": lead.score,
                "segment": lead.priority_level,
                "status": lead.status.value,
                "website_quality_score": lead.website_quality_score,
                "seo_score": lead.seo_score,
                "geo_score": lead.geo_score,
                "is_mobile_friendly": lead.is_mobile_friendly,
                "has_booking_system": lead.has_booking_system,
                "room_count": lead.room_count,
                "capacity": lead.capacity,
                "notes": lead.notes,
            },
        )

    async def _tool_analyze_website(self, params: dict) -> ToolResult:
        """Analyse le site web d'un lead."""
        lead_id = params.get("lead_id")

        result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()

        if not lead:
            return ToolResult(
                success=False, data=None, error=f"Lead {lead_id} non trouvé"
            )

        if not lead.website or lead.website == "-":
            return ToolResult(
                success=True,
                data={
                    "lead_id": lead_id,
                    "has_website": False,
                    "message": "Ce lead n'a pas de site web - excellent prospect pour création de site!",
                },
            )

        # Analyser le site (WebsiteAnalyzer.analyze() retourne un WebsiteAnalysisResult dataclass)
        analysis = await self.website_analyzer.analyze(lead.website)

        if analysis.success:
            # Mettre à jour le lead avec les attributs du dataclass
            lead.has_website = True
            lead.website_quality_score = analysis.quality_score
            lead.seo_score = analysis.seo_score
            lead.geo_score = analysis.geo_score
            lead.is_mobile_friendly = analysis.is_mobile_friendly
            lead.has_booking_system = analysis.has_booking_system
            lead.website_audit = build_website_audit(analysis)
            lead.update_score()
            await self.db.commit()

            return ToolResult(
                success=True,
                data={
                    "lead_id": lead_id,
                    "website": lead.website,
                    "accessible": True,
                    "quality_score": analysis.quality_score,
                    "seo_score": analysis.seo_score,
                    "geo_score": analysis.geo_score,
                    "geo_details": {
                        "has_structured_data": analysis.has_structured_data,
                        "has_faq_schema": analysis.has_faq_schema,
                        "has_local_business": analysis.has_local_business,
                        "content_richness": analysis.content_richness,
                    },
                    "is_mobile_friendly": analysis.is_mobile_friendly,
                    "has_booking_system": analysis.has_booking_system,
                    "load_time_ms": analysis.load_time_ms,
                    "new_segment": lead.priority_level,
                    "new_score": lead.score,
                },
            )

        # Site inaccessible
        lead.has_website = False
        await self.db.commit()
        return ToolResult(
            success=True,
            data={
                "lead_id": lead_id,
                "website": lead.website,
                "accessible": False,
                "error": analysis.error,
                "message": f"Site inaccessible: {analysis.error or 'erreur inconnue'} - adapter le message de prospection.",
            },
        )

    async def _tool_analyze_google_reviews(self, params: dict) -> ToolResult:
        """Analyse les avis Google d'un lead."""
        lead_id = params.get("lead_id")
        force_refresh = params.get("force_refresh", False)

        result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()

        if not lead:
            return ToolResult(
                success=False, data=None, error=f"Lead {lead_id} non trouvé"
            )

        # Vérifier si déjà analysé (sauf si force_refresh)
        if lead.google_reviews_analyzed_at and not force_refresh:
            return ToolResult(
                success=True,
                data={
                    "lead_id": lead_id,
                    "lead_name": lead.name,
                    "already_analyzed": True,
                    "rating": lead.google_rating,
                    "reviews_count": lead.google_reviews_count,
                    "frequency": lead.google_reviews_frequency,
                    "trend": lead.google_reviews_trend,
                    "period_months": lead.google_reviews_period_months,
                    "message": "Données déjà disponibles (utilisez force_refresh=true pour réanalyser)",
                },
            )

        # Lancer l'analyse
        service = get_google_reviews_service()
        reviews_data = await service.analyze_establishment(
            name=lead.name,
            city=lead.city,
            address=lead.address,
            place_id=lead.google_place_id,
        )

        if not reviews_data:
            return ToolResult(
                success=True,
                data={
                    "lead_id": lead_id,
                    "lead_name": lead.name,
                    "found": False,
                    "message": "Établissement non trouvé sur Google Maps - vérifier le nom/adresse",
                },
            )

        # Mettre à jour le lead
        lead.google_place_id = reviews_data.place_id
        lead.google_rating = reviews_data.rating
        lead.google_reviews_count = reviews_data.reviews_count
        lead.google_reviews_period_months = reviews_data.period_months
        lead.google_reviews_frequency = reviews_data.frequency
        lead.google_reviews_trend = reviews_data.trend
        lead.google_reviews_analyzed_at = reviews_data.analyzed_at
        lead.update_score()

        await self.db.commit()

        # Construire une interprétation utile pour l'agent
        interpretation = []
        if reviews_data.rating >= 4.5:
            interpretation.append(
                "⭐ Excellente réputation - argument pour site premium"
            )
        elif reviews_data.rating < 3.5:
            interpretation.append("⚠️ Réputation fragile - besoin de gestion d'image")

        if reviews_data.trend == "growing":
            interpretation.append("📈 Activité en croissance - bon moment pour investir")
        elif reviews_data.trend == "declining":
            interpretation.append("📉 Activité en déclin - besoin de visibilité")

        if reviews_data.frequency >= 5:
            interpretation.append("🔥 Très actif - établissement populaire")
        elif reviews_data.frequency < 0.5:
            interpretation.append("😴 Peu d'activité - besoin de visibilité")

        return ToolResult(
            success=True,
            data={
                "lead_id": lead_id,
                "lead_name": lead.name,
                "found": True,
                "rating": reviews_data.rating,
                "reviews_count": reviews_data.reviews_count,
                "frequency": reviews_data.frequency,
                "frequency_label": f"{reviews_data.frequency} avis/mois",
                "trend": reviews_data.trend,
                "period_months": reviews_data.period_months,
                "new_score": lead.score,
                "new_segment": lead.priority_level,
                "interpretation": interpretation,
            },
        )

    async def _tool_generate_message(self, params: dict) -> ToolResult:
        """Génère un message personnalisé."""
        lead_id = params.get("lead_id")

        result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()

        if not lead:
            return ToolResult(
                success=False, data=None, error=f"Lead {lead_id} non trouvé"
            )

        channel = MessageChannel(params.get("channel", "email"))
        tone = MessageTone(params.get("tone", "friendly"))

        message = self.ai_service.generate_message(
            lead=lead,
            channel=channel,
            tone=tone,
            custom_instructions=params.get("custom_instructions"),
        )

        return ToolResult(
            success=True,
            data={
                "lead_id": lead_id,
                "lead_name": lead.name,
                "segment": lead.priority_level,
                "channel": channel.value,
                "tone": tone.value,
                "subject": message.subject,
                "body": message.body,
                "personalization_points": message.personalization_points,
            },
        )

    async def _tool_queue_email(self, params: dict) -> ToolResult:
        """Met un email en file d'attente."""
        lead_id = params.get("lead_id")
        requires_approval = params.get("requires_approval", True)

        result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()

        if not lead:
            return ToolResult(
                success=False, data=None, error=f"Lead {lead_id} non trouvé"
            )

        if not lead.email:
            return ToolResult(
                success=False,
                data=None,
                error=f"Le lead {lead.name} n'a pas d'adresse email",
            )

        # En mode supervisé ou manuel, demander validation
        if self.state.mode != AgentMode.AUTONOMOUS:
            return ToolResult(
                success=True,
                data={
                    "status": "pending_approval",
                    "lead_id": lead_id,
                    "lead_name": lead.name,
                    "to_email": lead.email,
                    "subject": params.get("subject"),
                    "body": params.get("body"),
                    "question": f"Voulez-vous envoyer cet email à {lead.name} ({lead.email}) ?",
                },
                requires_human_action=True,
            )

        # Mode autonome : envoi réel via SMTP
        subject = params.get("subject", "Proposition Kawanah Tourisme")
        body = params.get("body", "")

        result = send_prospection_email(
            to_email=lead.email,
            subject=subject,
            body=body,
        )

        if not result.success:
            return ToolResult(
                success=False,
                data=None,
                error=f"Échec d'envoi à {lead.email}: {result.error}",
            )

        self.state.completed_actions.append(
            {
                "type": "send_email",
                "lead_id": lead_id,
                "to": lead.email,
                "subject": subject,
            }
        )

        return ToolResult(
            success=True,
            data={
                "status": "sent",
                "lead_id": lead_id,
                "lead_name": lead.name,
                "to_email": lead.email,
                "message": f"Email envoyé à {lead.name} ({lead.email})",
            },
        )

    async def _tool_update_status(self, params: dict) -> ToolResult:
        """Met à jour le statut d'un lead."""
        lead_id = params.get("lead_id")
        new_status = params.get("status")

        result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()

        if not lead:
            return ToolResult(
                success=False, data=None, error=f"Lead {lead_id} non trouvé"
            )

        old_status = lead.status.value
        lead.status = LeadStatus(new_status)

        if params.get("notes"):
            existing_notes = lead.notes or ""
            lead.notes = (
                f"{existing_notes}\n[{datetime.utcnow().isoformat()}] {params['notes']}"
            )

        await self.db.commit()

        return ToolResult(
            success=True,
            data={
                "lead_id": lead_id,
                "lead_name": lead.name,
                "old_status": old_status,
                "new_status": new_status,
            },
        )

    async def _tool_get_stats(self, params: dict) -> ToolResult:
        """Récupère les statistiques de campagne via des requêtes SQL agrégées."""
        # URLs invalides (même logique que has_valid_website_url dans le modèle Lead)
        invalid_urls = ["-", "n/a", "na", "none", "null", ""]

        # Helper: condition "a une URL de site valide"
        from sqlalchemy import case, cast, Integer

        has_valid_url = (
            Lead.website.isnot(None)
            & ~func.lower(func.trim(Lead.website)).in_(invalid_urls)
            & (func.length(func.trim(Lead.website)) > 3)
        )

        # SANS SITE: pas d'URL valide
        sans_site_q = await self.db.execute(
            select(func.count(Lead.id)).where(~has_valid_url)
        )
        sans_site = sans_site_q.scalar() or 0

        # À VÉRIFIER: URL valide + non analysé + site inaccessible
        a_verifier_q = await self.db.execute(
            select(func.count(Lead.id)).where(
                has_valid_url,
                Lead.website_quality_score.is_(None),
                Lead.has_website == False,  # noqa: E712
            )
        )
        a_verifier = a_verifier_q.scalar() or 0

        # CHAUD: URL valide + score >= 80
        chaud_q = await self.db.execute(
            select(func.count(Lead.id)).where(has_valid_url, Lead.score >= 80)
        )
        chaud = chaud_q.scalar() or 0

        # TIÈDE: URL valide + 50 <= score < 80
        tiede_q = await self.db.execute(
            select(func.count(Lead.id)).where(
                has_valid_url, Lead.score >= 50, Lead.score < 80
            )
        )
        tiede = tiede_q.scalar() or 0

        # FROID: URL valide + score < 50
        froid_q = await self.db.execute(
            select(func.count(Lead.id)).where(has_valid_url, Lead.score < 50)
        )
        froid = froid_q.scalar() or 0

        # Total
        total_q = await self.db.execute(select(func.count(Lead.id)))
        total = total_q.scalar() or 0

        # Par statut (requête groupée)
        statuses_q = await self.db.execute(
            select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
        )
        statuses = {row[0].value: row[1] for row in statuses_q}

        return ToolResult(
            success=True,
            data={
                "total_leads": total,
                "by_segment": {
                    "sans_site": sans_site,
                    "a_verifier": a_verifier,
                    "chaud": chaud,
                    "tiede": tiede,
                    "froid": froid,
                },
                "by_status": statuses,
                "hot_prospects": sans_site + chaud,
                "pending_actions": len(self.state.pending_actions),
            },
        )

    async def _tool_verify_website(self, params: dict) -> ToolResult:
        """
        Vérifie si un établissement a réellement un site web.
        IMPORTANT: Utiliser AVANT d'envoyer un email à un lead 'SANS SITE'.
        """
        lead_id = params.get("lead_id")
        establishment_name = params.get("establishment_name")
        city = params.get("city")

        # Si on a un lead_id, récupérer les infos du lead
        if lead_id:
            result = await self.db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()

            if not lead:
                return ToolResult(
                    success=False, data=None, error=f"Lead {lead_id} non trouvé"
                )

            establishment_name = lead.name
            city = lead.city
            current_url = lead.website
        else:
            current_url = None

        if not establishment_name:
            return ToolResult(
                success=False,
                data=None,
                error="Nom de l'établissement requis (lead_id ou establishment_name)",
            )

        # Effectuer la vérification
        verification = await verify_establishment_website(
            name=establishment_name, city=city, current_url=current_url
        )

        # Si on a trouvé un site et qu'on a un lead_id, proposer la mise à jour
        if verification["has_website"] and lead_id and verification["found_url"]:
            return ToolResult(
                success=True,
                data={
                    "lead_id": lead_id,
                    "establishment": establishment_name,
                    "has_website": True,
                    "found_url": verification["found_url"],
                    "confidence": verification["confidence"],
                    "warning": "⚠️ ATTENTION: Ce lead a un site web! Ne pas envoyer d'email 'vous n'avez pas de site'.",
                    "recommendation": verification["recommendation"],
                    "action_suggested": "Mettre à jour le lead avec cette URL et adapter le message de prospection.",
                },
            )

        return ToolResult(
            success=True,
            data={
                "lead_id": lead_id,
                "establishment": establishment_name,
                "has_website": verification["has_website"],
                "found_url": verification["found_url"],
                "confidence": verification["confidence"],
                "recommendation": verification["recommendation"],
            },
        )

    async def _tool_request_human(self, params: dict) -> ToolResult:
        """Demande une décision humaine."""
        return ToolResult(
            success=True,
            data={
                "question": params.get("question"),
                "options": params.get("options", []),
                "context": params.get("context", ""),
            },
            requires_human_action=True,
        )

    async def _demo_response(self, user_message: str) -> str:
        """Réponse de démo sans API Claude."""
        user_lower = user_message.lower()

        # Mots-clés de recherche
        search_keywords = [
            "prospect",
            "lead",
            "cherch",
            "trouve",
            "hôtel",
            "hotel",
            "camping",
            "gîte",
            "gite",
            "liste",
            "montre",
            "affiche",
        ]

        # Détecter une recherche
        is_search = any(kw in user_lower for kw in search_keywords)

        if is_search:
            # Déterminer le segment demandé
            segment = "all"
            if "sans site" in user_lower or "pas de site" in user_lower:
                segment = "sans_site"
            elif "chaud" in user_lower:
                segment = "chaud"
            elif "tiède" in user_lower or "tiede" in user_lower:
                segment = "tiede"
            elif "froid" in user_lower:
                segment = "froid"
            elif "vérifier" in user_lower or "verifier" in user_lower:
                segment = "a_verifier"

            # Déterminer le type
            lead_type = None
            if "hôtel" in user_lower or "hotel" in user_lower:
                lead_type = "hotel"
            elif "camping" in user_lower:
                lead_type = "camping"
            elif "gîte" in user_lower or "gite" in user_lower:
                lead_type = "gite"

            # Faire la recherche
            search_params = {"segment": segment, "limit": 10}
            if lead_type:
                search_params["lead_type"] = lead_type

            result = await self._tool_search_leads(search_params)
            leads = result.data.get("leads", [])

            segment_labels = {
                "all": "tous segments",
                "sans_site": "🔥 SANS SITE",
                "chaud": "🔥 CHAUD",
                "tiede": "😐 TIÈDE",
                "froid": "❄️ FROID",
                "a_verifier": "⚠️ À VÉRIFIER",
            }

            response = f"📊 **Recherche de prospects** ({segment_labels.get(segment, segment)})\n\n"

            if not leads:
                response += "Aucun lead trouvé avec ces critères.\n"
            else:
                response += f"J'ai trouvé **{len(leads)}** leads :\n\n"
                for lead in leads:
                    response += f"• **{lead['name']}** ({lead['city'] or 'N/A'}) - {lead['segment']} - Score: {lead['score']}\n"

            response += (
                "\n💡 *Mode démo - Configurez ANTHROPIC_API_KEY pour l'agent complet*"
            )
            return response

        elif "stat" in user_lower:
            result = await self._tool_get_stats({})
            stats = result.data

            return f"""📈 **Statistiques de prospection**

**Total leads:** {stats['total_leads']}

**Par segment:**
- 🔥 Sans site: {stats['by_segment']['sans_site']}
- ⚠️ À vérifier: {stats['by_segment']['a_verifier']}
- 🔥 Chaud: {stats['by_segment']['chaud']}
- 😐 Tiède: {stats['by_segment']['tiede']}
- ❄️ Froid: {stats['by_segment']['froid']}

**Prospects prioritaires:** {stats['hot_prospects']}

💡 *Mode démo - Configurez ANTHROPIC_API_KEY pour activer l'agent complet*"""

        else:
            return """👋 **Agent de Prospection Kawanah Tourisme**

Je suis votre assistant de prospection. Voici ce que je peux faire :

🔍 **Rechercher** - "Trouve-moi des hôtels sans site web"
📊 **Analyser** - "Analyse le site de ce prospect"
✉️ **Rédiger** - "Génère un email pour ce lead"
📈 **Statistiques** - "Montre-moi les stats"

Essayez de me demander quelque chose !

💡 *Mode démo - Configurez ANTHROPIC_API_KEY pour activer l'agent complet avec IA*"""

    def reset_conversation(self):
        """Réinitialise la conversation."""
        self.state.conversation_history = []
        self.state.requires_human_input = False
        self.state.human_question = None
