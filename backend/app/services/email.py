import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict

from app.core.config import settings

logger = logging.getLogger("NetVision.Email")

# Memory store for development/testing inspection
latest_dev_email: Optional[Dict[str, str]] = None

def send_password_reset_email(email: str, reset_token: str) -> Dict[str, str]:
    """
    Send password reset email via SMTP if configured, 
    otherwise log dev-safe reset URL in development mode.
    """
    global latest_dev_email
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    
    dev_info = {
        "email": email,
        "reset_url": reset_url,
        "token": reset_token
    }
    latest_dev_email = dev_info

    if settings.SMTP_HOST:
        try:
            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_FROM_EMAIL
            msg["To"] = email
            msg["Subject"] = "NetVision - Password Reset Request"

            body = (
                f"Hello,\n\n"
                f"A password reset was requested for your NetVision account.\n"
                f"Please click the link below to reset your password:\n\n"
                f"{reset_url}\n\n"
                f"This link will expire in {settings.RESET_TOKEN_EXPIRE_MINUTES} minutes.\n"
                f"If you did not request a password reset, please ignore this email.\n"
            )
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Password reset email sent successfully to {email}")
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")
            if settings.ENVIRONMENT != "development":
                raise e
    else:
        # Development mode fallback when SMTP is not configured
        logger.info(
            f"[DEVELOPMENT ONLY] SMTP not configured. "
            f"Password reset link generated for {email}: {reset_url}"
        )

    return dev_info
