"""
Service d'envoi d'emails via SMTP.
"""

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
    ) -> EmailResult:
        """
        Envoie un email.

        Args:
            to_email: Adresse email du destinataire
            subject: Objet de l'email
            body: Corps de l'email (texte brut)
            html_body: Corps HTML (optionnel)
        """
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

            # Connexion SMTP avec TLS — certificats vérifiés via certifi
            context = ssl.create_default_context(cafile=certifi.where())

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


def send_prospection_email(
    to_email: str,
    lead_name: str,
    subject: str,
    body: str,
) -> EmailResult:
    """
    Envoie un email de prospection.
    Helper function pour l'API.
    """
    service = EmailService()

    # Créer une version HTML simple
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            {body.replace(chr(10), '<br>')}
            <div class="footer">
                <p>Cet email a été envoyé par l'Agent de Prospection Kawanah Travel.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return service.send_email(to_email, subject, body, html_body)
