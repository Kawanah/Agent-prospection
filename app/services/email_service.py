"""
Service d'envoi d'emails via SMTP.
"""

import html
import re
import smtplib
import ssl
import certifi
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from dataclasses import dataclass

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _validate_email(email: str) -> str:
    """Valide et nettoie une adresse email. Lève ValueError si invalide."""
    email = email.strip()
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Adresse email invalide : {email!r}")
    return email


from loguru import logger

from app.config import get_settings

settings = get_settings()


@dataclass
class EmailResult:
    """Résultat d'un envoi d'email."""

    success: bool
    to_email: str
    subject: str
    error: Optional[str] = None
    dry_run: bool = False


class EmailService:
    """Service d'envoi d'emails via SMTP."""

    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password
        self.email_from = settings.email_from

    def is_configured(self) -> bool:
        """Vérifie si le service email est configuré."""
        return all(
            [
                self.smtp_host,
                self.smtp_port,
                self.smtp_user,
                self.smtp_password,
                self.email_from,
            ]
        )

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        force_send: bool = False,
    ) -> EmailResult:
        """
        Envoie un email.

        SÉCURITÉ : les envois réels sont bloqués tant que
        ENABLE_EMAIL_DELIVERY=false. Le mode dev/test ne contacte jamais SMTP.
        """
        if not settings.enable_email_delivery:
            try:
                to_email = _validate_email(to_email)
            except ValueError as exc:
                return EmailResult(
                    success=False,
                    to_email=to_email,
                    subject=subject,
                    error=str(exc),
                    dry_run=True,
                )
            logger.warning(
                f"⚠️ ENVOI SIMULÉ (mode {settings.app_env}, ENABLE_EMAIL_DELIVERY=false) - "
                f"Destinataire: {to_email}, Objet: {subject}"
            )
            return EmailResult(
                success=False,
                to_email=to_email,
                subject=subject,
                error="Envoi réel désactivé : simulation développement/test.",
                dry_run=True,
            )

        if settings.app_env != "production" and not force_send:
            logger.warning(
                f"⚠️ ENVOI BLOQUÉ (mode {settings.app_env}) - "
                f"Destinataire: {to_email}, Objet: {subject}"
            )
            return EmailResult(
                success=False,
                to_email=to_email,
                subject=subject,
                error=f"Envoi bloqué en mode {settings.app_env}. Passez APP_ENV=production.",
            )

        if not self.is_configured():
            return EmailResult(
                success=False,
                to_email=to_email,
                subject=subject,
                error="Service email non configuré. Vérifiez les variables SMTP dans .env",
            )

        try:
            # Valider l'email destinataire avant tout envoi
            to_email = _validate_email(to_email)

            # Créer le message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.email_from
            message["To"] = to_email

            # Ajouter le corps texte
            part1 = MIMEText(body, "plain", "utf-8")
            message.attach(part1)

            # Ajouter le corps HTML si fourni
            if html_body:
                part2 = MIMEText(html_body, "html", "utf-8")
                message.attach(part2)

            # Connexion SMTP — SSL direct (port 465) ou STARTTLS (port 587)
            context = ssl.create_default_context(cafile=certifi.where())

            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(
                    self.smtp_host, self.smtp_port, context=context
                ) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.email_from, to_email, message.as_string())
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.email_from, to_email, message.as_string())

            logger.info(f"✅ Email envoyé à {to_email}: {subject}")

            return EmailResult(success=True, to_email=to_email, subject=subject)

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"Erreur d'authentification SMTP: {e}"
            logger.error(error_msg)
            return EmailResult(
                success=False, to_email=to_email, subject=subject, error=error_msg
            )

        except smtplib.SMTPException as e:
            error_msg = f"Erreur SMTP: {e}"
            logger.error(error_msg)
            return EmailResult(
                success=False, to_email=to_email, subject=subject, error=error_msg
            )

        except Exception as e:
            error_msg = f"Erreur envoi email: {e}"
            logger.error(error_msg)
            return EmailResult(
                success=False, to_email=to_email, subject=subject, error=error_msg
            )

    def send_bulk(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> List[EmailResult]:
        """
        Envoie un email à plusieurs destinataires.
        """
        results = []
        for to_email in recipients:
            result = self.send_email(to_email, subject, body, html_body)
            results.append(result)
        return results


def _linkify(text: str) -> str:
    """Convertit les URLs en liens cliquables dans un texte HTML déjà échappé."""
    # Détecte les URLs (http/https et les domaines nus type tourisme.kawanah.com)
    url_pattern = re.compile(
        r'(https?://[^\s<>"]+|(?<!\w)([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s<>"]*)?)'
    )

    def replace_url(m):
        url = m.group(0)
        href = url if url.startswith("http") else f"https://{url}"
        return f'<a href="{href}" style="color:#1a6b8a;text-decoration:none;">{url}</a>'

    return url_pattern.sub(replace_url, text)


def send_prospection_email(
    to_email: str,
    subject: str,
    body: str,
    force_send: bool = False,
) -> EmailResult:
    """
    Envoie un email de prospection.
    Helper function pour l'API.

    SÉCURITÉ : les emails ne partent pas tant que ENABLE_EMAIL_DELIVERY=false.
    """
    if not settings.enable_email_delivery:
        logger.warning(
            f"⚠️ ENVOI SIMULÉ (ENABLE_EMAIL_DELIVERY=false) - Destinataire: {to_email}, Objet: {subject}."
        )
        return EmailResult(
            success=False,
            to_email=to_email,
            subject=subject,
            error="Envoi réel désactivé : simulation développement/test.",
            dry_run=True,
        )

    service = EmailService()

    # Convertir le corps en HTML avec liens cliquables
    escaped = html.escape(body)
    html_content = _linkify(escaped).replace("\n", "<br>")

    html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Georgia, serif; line-height: 1.7; color: #222; background: #fff; }}
        .container {{ max-width: 560px; margin: 0 auto; padding: 32px 24px; }}
        p {{ margin: 0 0 12px; }}
        .signature {{ margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee; font-size: 13px; color: #555; }}
    </style>
</head>
<body>
    <div class="container">
        {html_content}
    </div>
</body>
</html>"""

    return service.send_email(to_email, subject, body, html_body)
