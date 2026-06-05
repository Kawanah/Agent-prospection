"""
Service de séquençage — moteur d'envoi automatisé des campagnes.

Fonctionnement :
  1. launch_campaign()  → trouve les leads, génère les messages, les planifie
  2. process_queue()    → envoie les messages dont l'heure est venue (quota 50/jour, 60s entre chaque)
  3. schedule_followup() → programme les relances automatiques (J+N selon config campagne)
"""

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.lead import Lead, LeadStatus
from app.models.campaign import Campaign, CampaignStatus, CampaignChannel
from app.models.message import (
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    SentimentType,
)
from app.services.ai_service import AIService, MessageChannel as AIChannel, MessageTone
from app.services.email_service import EmailService
from app.config import get_settings

# ─── Constantes ───────────────────────────────────────────────────────────────

MAX_EMAILS_PER_DAY = 50  # Warm-up : ne pas dépasser 50 emails/jour
MIN_DELAY_SECONDS = 60  # Minimum 60s entre deux envois
FOLLOWUP_SUBJECT_PREFIX = "Re: "  # Préfixe objet des relances


# ─── Service principal ────────────────────────────────────────────────────────


class SequenceService:
    """Moteur d'envoi séquencé pour les campagnes de prospection."""

    def __init__(self):
        self.ai_service = AIService()
        self.email_service = EmailService()

    # ── 1. Lancement d'une campagne ───────────────────────────────────────────

    async def launch_campaign(
        self,
        campaign: Campaign,
        db: AsyncSession,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Génère et planifie les messages pour tous les leads éligibles.

        - Exclut les leads déjà contactés
        - Génère un message IA personnalisé pour chaque lead
        - Planifie l'envoi en respectant le quota journalier et les délais
        - Retourne le nombre de messages créés
        """
        # Trouver les leads éligibles (non encore contactés, avec email)
        query = (
            select(Lead)
            .where(
                Lead.status.in_([LeadStatus.NEW, LeadStatus.ENRICHED]),
                Lead.email.isnot(None),
                Lead.email != "",
            )
            .order_by(Lead.score.desc())  # Priorité aux meilleurs scores
        )
        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        leads = result.scalars().all()

        if not leads:
            return {
                "queued": 0,
                "message": "Aucun lead éligible (email requis, statut new/enriched)",
            }

        # Canal IA selon le canal de la campagne
        ai_channel = (
            AIChannel.EMAIL
            if campaign.channel == CampaignChannel.EMAIL
            else AIChannel.LINKEDIN
        )

        # Planifier les messages en espaçant de MIN_DELAY_SECONDS
        # On commence à "maintenant" pour le premier, puis on décale
        scheduled_at = datetime.utcnow()
        queued_count = 0

        for lead in leads:
            try:
                # Générer le message avec l'IA (ou démo si pas de clé)
                generated = self.ai_service.generate_message(
                    lead=lead,
                    channel=ai_channel,
                    tone=MessageTone.FRIENDLY,
                    sender_name="Laetitia",
                )

                message = Message(
                    campaign_id=campaign.id,
                    lead_id=lead.id,
                    channel=MessageChannel(ai_channel.value),
                    direction=MessageDirection.OUTBOUND,
                    status=MessageStatus.DRAFT,
                    subject=generated.subject,
                    body=generated.body,
                    sequence_number=1,
                    scheduled_at=None,
                )
                db.add(message)
                queued_count += 1

                # Espacer le prochain envoi
                scheduled_at += timedelta(seconds=MIN_DELAY_SECONDS)

                # Après MAX_EMAILS_PER_DAY messages, décaler au lendemain
                if queued_count % MAX_EMAILS_PER_DAY == 0:
                    scheduled_at = datetime.utcnow().replace(
                        hour=9, minute=0, second=0, microsecond=0
                    ) + timedelta(days=queued_count // MAX_EMAILS_PER_DAY)

            except Exception as e:
                logger.error(f"Erreur génération message pour lead {lead.id}: {e}")
                continue

        await db.commit()
        logger.info(
            f"Campagne {campaign.id} lancée : {queued_count} messages planifiés"
        )

        return {
            "queued": queued_count,
            "message": f"{queued_count} messages générés et planifiés",
        }

    # ── 1b. Ajout de leads spécifiques à une campagne ─────────────────────────

    async def add_leads(
        self,
        campaign: Campaign,
        lead_ids: list[int],
        db: AsyncSession,
    ) -> dict:
        """
        Génère et planifie les messages pour une liste de leads spécifiques.
        Même logique que launch_campaign mais ciblée sur des IDs précis.
        """
        from sqlalchemy import select as sa_select

        leads_result = await db.execute(sa_select(Lead).where(Lead.id.in_(lead_ids)))
        leads = leads_result.scalars().all()

        if not leads:
            return {"queued": 0, "message": "Aucun lead trouvé"}

        ai_channel = (
            AIChannel.EMAIL
            if campaign.channel == CampaignChannel.EMAIL
            else AIChannel.LINKEDIN
        )
        scheduled_at = datetime.utcnow()
        queued_count = 0

        for lead in leads:
            try:
                generated = self.ai_service.generate_message(
                    lead=lead,
                    channel=ai_channel,
                    tone=MessageTone.FRIENDLY,
                    sender_name="Laetitia",
                )
                message = Message(
                    campaign_id=campaign.id,
                    lead_id=lead.id,
                    channel=MessageChannel(ai_channel.value),
                    direction=MessageDirection.OUTBOUND,
                    status=MessageStatus.DRAFT,
                    subject=generated.subject,
                    body=generated.body,
                    sequence_number=1,
                    scheduled_at=None,
                )
                db.add(message)
                queued_count += 1
                scheduled_at += timedelta(seconds=MIN_DELAY_SECONDS)
            except Exception as e:
                logger.error(f"Erreur génération message pour lead {lead.id}: {e}")
                continue

        await db.commit()
        return {
            "queued": queued_count,
            "message": f"{queued_count} message(s) planifié(s)",
        }

    # ── 2. Traitement de la file d'attente ────────────────────────────────────

    async def process_queue(self, db: AsyncSession) -> dict:
        """
        Envoie les prochains messages de la file d'attente.

        - Vérifie le quota journalier (max MAX_EMAILS_PER_DAY)
        - Envoie le prochain message dont scheduled_at <= maintenant
        - Met à jour le statut du message et du lead
        - Programme la relance si configurée
        - Retourne un résumé de ce qui a été traité
        """
        current_settings = get_settings()
        if not current_settings.enable_email_delivery:
            return {
                "sent": 0,
                "failed": 0,
                "skipped": 0,
                "quota_reached": False,
                "dry_run": True,
                "message": "Envoi réel désactivé : file non traitée en mode développement/test.",
            }

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Vérifier le quota journalier
        sent_today_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.status.in_([MessageStatus.SENT, MessageStatus.DELIVERED]),
                Message.sent_at >= today_start,
                Message.direction == MessageDirection.OUTBOUND,
            )
        )
        sent_today = sent_today_result.scalar() or 0

        if sent_today >= MAX_EMAILS_PER_DAY:
            return {
                "sent": 0,
                "skipped": 0,
                "quota_reached": True,
                "message": f"Quota journalier atteint ({sent_today}/{MAX_EMAILS_PER_DAY}). Reprise demain.",
            }

        remaining_quota = MAX_EMAILS_PER_DAY - sent_today

        # Récupérer les messages en attente dont l'heure est venue
        queued_result = await db.execute(
            select(Message)
            .where(
                Message.status == MessageStatus.QUEUED,
                Message.direction == MessageDirection.OUTBOUND,
                Message.scheduled_at <= now,
            )
            .order_by(Message.scheduled_at.asc())
            .limit(remaining_quota)
        )
        messages = queued_result.scalars().all()

        if not messages:
            return {
                "sent": 0,
                "skipped": 0,
                "quota_reached": False,
                "message": "Aucun message à traiter pour le moment.",
            }

        sent_count = 0
        failed_count = 0

        for message in messages:
            # Récupérer le lead
            lead_result = await db.execute(
                select(Lead).where(Lead.id == message.lead_id)
            )
            lead = lead_result.scalar_one_or_none()

            if not lead:
                message.status = MessageStatus.FAILED
                await db.commit()
                failed_count += 1
                continue

            if not lead.email:
                # Compter combien de fois ce message a déjà été reporté (via scheduled_at)
                original_scheduled = message.created_at or now
                hours_delayed = (now - original_scheduled).total_seconds() / 3600

                if hours_delayed > 48:
                    # Après 48h sans email — passer en contact alternatif
                    lead.status = LeadStatus.NO_EMAIL
                    message.status = MessageStatus.FAILED
                    await db.commit()
                    logger.info(
                        f"Lead {lead.id} sans email depuis 48h — statut NO_EMAIL, message {message.id} annulé"
                    )
                else:
                    # Encore en attente — reporter de 24h
                    message.scheduled_at = message.scheduled_at + timedelta(hours=24)
                    await db.commit()
                    logger.info(
                        f"Lead {lead.id} sans email — message {message.id} reporté de 24h ({hours_delayed:.0f}h d'attente)"
                    )
                continue

            # Envoyer l'email
            result = self.email_service.send_email(
                to_email=lead.email,
                subject=message.subject or "Votre présence en ligne",
                body=message.body,
            )

            if result.success:
                # Mettre à jour le message
                message.status = MessageStatus.SENT
                message.sent_at = datetime.utcnow()

                # Mettre à jour le statut du lead
                lead.status = LeadStatus.CONTACTED

                # Mettre à jour les stats de la campagne
                if message.campaign_id:
                    campaign_result = await db.execute(
                        select(Campaign).where(Campaign.id == message.campaign_id)
                    )
                    campaign = campaign_result.scalar_one_or_none()
                    if campaign:
                        campaign.emails_sent = (campaign.emails_sent or 0) + 1
                        campaign.total_leads = (campaign.total_leads or 0) + 1

                        # Planifier la relance si configurée
                        if (
                            campaign.max_follow_ups > 0
                            and message.sequence_number < campaign.max_follow_ups + 1
                        ):
                            await self._schedule_followup(message, campaign, lead, db)

                sent_count += 1
                logger.info(
                    f"Email envoyé à {lead.email} (lead {lead.id}, message {message.id})"
                )

            else:
                message.status = MessageStatus.FAILED
                failed_count += 1
                logger.warning(f"Échec envoi à {lead.email}: {result.error}")

            await db.commit()

        return {
            "sent": sent_count,
            "failed": failed_count,
            "quota_reached": (sent_today + sent_count) >= MAX_EMAILS_PER_DAY,
            "remaining_today": MAX_EMAILS_PER_DAY - sent_today - sent_count,
            "message": f"{sent_count} emails envoyés, {failed_count} échecs.",
        }

    # ── 3. Planification des relances ─────────────────────────────────────────

    async def _schedule_followup(
        self,
        original_message: Message,
        campaign: Campaign,
        lead: Lead,
        db: AsyncSession,
    ) -> None:
        """
        Programme une relance automatique après le délai configuré dans la campagne.
        Ne crée pas de relance si le lead a déjà répondu.
        """
        # Vérifier si une relance existe déjà
        existing_followup = await db.execute(
            select(Message).where(
                Message.lead_id == lead.id,
                Message.campaign_id == campaign.id,
                Message.sequence_number == original_message.sequence_number + 1,
                Message.status == MessageStatus.QUEUED,
            )
        )
        if existing_followup.scalar_one_or_none():
            return  # Relance déjà planifiée

        followup_date = datetime.utcnow() + timedelta(days=campaign.follow_up_days)

        # Générer le message de relance
        ai_channel = (
            AIChannel.EMAIL
            if campaign.channel == CampaignChannel.EMAIL
            else AIChannel.LINKEDIN
        )
        try:
            generated = self.ai_service.generate_message(
                lead=lead,
                channel=ai_channel,
                tone=MessageTone.FRIENDLY,
                sender_name="Laetitia",
                custom_instructions=f"C'est une relance (message {original_message.sequence_number + 1}). "
                f"Mentionner brièvement le premier contact sans réponse. Rester bref.",
            )

            followup = Message(
                campaign_id=campaign.id,
                lead_id=lead.id,
                channel=MessageChannel(ai_channel.value),
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.QUEUED,
                subject=f"{FOLLOWUP_SUBJECT_PREFIX}{original_message.subject or 'Votre présence en ligne'}",
                body=generated.body,
                sequence_number=original_message.sequence_number + 1,
                parent_message_id=original_message.id,
                scheduled_at=followup_date,
            )
            db.add(followup)
            logger.info(
                f"Relance planifiée pour lead {lead.id} "
                f"(J+{campaign.follow_up_days}, séquence {followup.sequence_number})"
            )
        except Exception as e:
            logger.error(f"Erreur création relance pour lead {lead.id}: {e}")

    # ── 4. Stats de la file d'attente ─────────────────────────────────────────

    async def get_queue_stats(self, db: AsyncSession) -> dict:
        """Retourne les statistiques actuelles de la file d'attente."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        queued = await db.execute(
            select(func.count(Message.id)).where(
                Message.status == MessageStatus.QUEUED,
                Message.direction == MessageDirection.OUTBOUND,
            )
        )
        ready_now = await db.execute(
            select(func.count(Message.id)).where(
                Message.status == MessageStatus.QUEUED,
                Message.direction == MessageDirection.OUTBOUND,
                Message.scheduled_at <= now,
            )
        )
        sent_today = await db.execute(
            select(func.count(Message.id)).where(
                Message.status.in_([MessageStatus.SENT, MessageStatus.DELIVERED]),
                Message.sent_at >= today_start,
                Message.direction == MessageDirection.OUTBOUND,
            )
        )
        failed = await db.execute(
            select(func.count(Message.id)).where(
                Message.status == MessageStatus.FAILED,
                Message.direction == MessageDirection.OUTBOUND,
            )
        )

        sent_today_val = sent_today.scalar() or 0

        return {
            "queued_total": queued.scalar() or 0,
            "ready_now": ready_now.scalar() or 0,
            "sent_today": sent_today_val,
            "quota_remaining_today": max(0, MAX_EMAILS_PER_DAY - sent_today_val),
            "quota_limit": MAX_EMAILS_PER_DAY,
            "failed_total": failed.scalar() or 0,
            "email_delivery_enabled": get_settings().enable_email_delivery,
        }
