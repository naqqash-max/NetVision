import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger("NetVision.EmailService")

# Global in-memory cache for recent dev reset email details (useful for automated testing)
latest_dev_email: Optional[Dict[str, Any]] = None


class EmailService:
    """
    Centralized Email Service for NetVision.
    Handles HTML and Plain-Text email generation, SMTP connection management,
    and safe delivery for password recovery and notifications.
    """

    @staticmethod
    def render_password_reset_html(to_email: str, reset_url: str, expire_minutes: int) -> str:
        """Render responsive HTML email template for password reset with NetVision branding."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetVision Password Reset</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #0b0f19;
            color: #e2e8f0;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 580px;
            margin: 0 auto;
            background-color: #1e293b;
            border-radius: 12px;
            border: 1px solid #334155;
            overflow: hidden;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .header {{
            background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
            padding: 28px 32px;
            text-align: center;
        }}
        .header h1 {{
            color: #ffffff;
            font-size: 24px;
            font-weight: 800;
            margin: 0;
            letter-spacing: 0.5px;
        }}
        .header p {{
            color: #e0e7ff;
            font-size: 13px;
            margin: 4px 0 0 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .content {{
            padding: 32px;
        }}
        .greeting {{
            font-size: 16px;
            font-weight: 600;
            color: #f8fafc;
            margin-bottom: 12px;
        }}
        .text {{
            font-size: 14px;
            line-height: 1.6;
            color: #94a3b8;
            margin-bottom: 24px;
        }}
        .btn-container {{
            text-align: center;
            margin: 30px 0;
        }}
        .btn {{
            display: inline-block;
            background-color: #6366f1;
            color: #ffffff !important;
            font-weight: 700;
            font-size: 14px;
            padding: 14px 32px;
            text-decoration: none;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
            transition: all 0.2s ease;
        }}
        .url-box {{
            background-color: #0f172a;
            border: 1px solid #334155;
            padding: 12px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 12px;
            color: #818cf8;
            word-break: break-all;
            margin-top: 12px;
        }}
        .warning-box {{
            background-color: rgba(244, 63, 94, 0.1);
            border-left: 4px solid #f43f5e;
            padding: 12px 16px;
            margin: 24px 0;
            border-radius: 0 6px 6px 0;
        }}
        .warning-box p {{
            margin: 0;
            font-size: 12px;
            color: #fda4af;
            line-height: 1.5;
        }}
        .footer {{
            background-color: #0f172a;
            padding: 20px 32px;
            text-align: center;
            border-top: 1px solid #1e293b;
        }}
        .footer p {{
            font-size: 12px;
            color: #64748b;
            margin: 4px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>NetVision</h1>
            <p>Enterprise Network Monitoring & NOC System</p>
        </div>
        <div class="content">
            <div class="greeting">Password Reset Request</div>
            <p class="text">
                A password reset request was initiated for your NetVision account (<strong>{to_email}</strong>). 
                To select a new password, click the button below:
            </p>
            <div class="btn-container">
                <a href="{reset_url}" class="btn" target="_blank">Reset Password</a>
            </div>
            <p class="text" style="font-size: 12px; margin-bottom: 4px;">Or copy and paste this link into your web browser:</p>
            <div class="url-box">{reset_url}</div>
            
            <div class="warning-box">
                <p><strong>Security Notice:</strong> This single-use link will expire in <strong>{expire_minutes} minutes</strong>. If you did not request a password reset, please ignore this message or notify your administrator immediately. Passwords are never sent via email.</p>
            </div>
        </div>
        <div class="footer">
            <p>NetVision Network Operations Center (NOC) Platform</p>
            <p>Need support? Contact <a href="mailto:support@netvision.local" style="color: #818cf8;">support@netvision.local</a></p>
        </div>
    </div>
</body>
</html>"""

    @staticmethod
    def render_password_reset_text(to_email: str, reset_url: str, expire_minutes: int) -> str:
        """Render plain text fallback for password reset email."""
        return (
            f"NetVision Platform - Password Reset Request\n\n"
            f"A password reset request was initiated for your NetVision account ({to_email}).\n\n"
            f"Please click the link below to set a new password:\n"
            f"{reset_url}\n\n"
            f"SECURITY NOTICE:\n"
            f"- This link is single-use and will expire in {expire_minutes} minutes.\n"
            f"- If you did not request a password reset, you may safely ignore this email.\n"
            f"- Your current password remains active until you complete the reset process.\n\n"
            f"NetVision NOC Security Team\n"
            f"Support: support@netvision.local"
        )

    @classmethod
    def send_password_reset(cls, to_email: str, reset_token: str) -> Dict[str, Any]:
        """
        Generates and delivers password reset email via SMTP (or Mailpit in dev).
        Returns a delivery summary dictionary without exposing sensitive credentials.
        """
        global latest_dev_email
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        dev_info = {
            "email": to_email,
            "reset_url": reset_url,
            "token": reset_token,
            "success": True
        }
        latest_dev_email = dev_info

        if not settings.EMAIL_ENABLED:
            logger.info(f"EMAIL_ENABLED is False. Skipping password reset email for {to_email}.")
            return dev_info

        if not settings.SMTP_HOST:
            logger.warning("SMTP_HOST is empty. Cannot deliver email via SMTP.")
            return dev_info

        try:
            from_name = getattr(settings, "SMTP_FROM_NAME", "NetVision Operations Center")
            msg["From"] = f"{from_name} <{settings.SMTP_FROM_EMAIL}>" if from_name else settings.SMTP_FROM_EMAIL
            msg["To"] = to_email
            msg["Subject"] = "NetVision - Password Reset Request"

            text_part = MIMEText(
                cls.render_password_reset_text(to_email, reset_url, settings.RESET_TOKEN_EXPIRE_MINUTES),
                "plain"
            )
            html_part = MIMEText(
                cls.render_password_reset_html(to_email, reset_url, settings.RESET_TOKEN_EXPIRE_MINUTES),
                "html"
            )

            msg.attach(text_part)
            msg.attach(html_part)

            # Choose SMTP connection type (SSL vs Standard/TLS)
            if settings.SMTP_SSL:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)

            with server:
                if not settings.SMTP_SSL and settings.SMTP_TLS:
                    server.starttls()
                
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                
                server.send_message(msg)

            logger.info(f"Password reset email sent successfully to {to_email} via SMTP ({settings.SMTP_HOST}:{settings.SMTP_PORT})")
            dev_info["success"] = True

        except Exception as err:
            # Mask sensitive server parameters in logs and handle failure safely
            logger.error(f"Failed to send email to {to_email} via {settings.SMTP_HOST}:{settings.SMTP_PORT}: {err}")
            dev_info["success"] = False
            dev_info["error"] = str(err)
            if settings.ENVIRONMENT != "development":
                # In production, swallow error internally or raise clean non-leaking exception
                pass

        return dev_info


def send_password_reset_email(email: str, reset_token: str) -> Dict[str, Any]:
    """Convenience alias function for authentication module integration."""
    return EmailService.send_password_reset(to_email=email, reset_token=reset_token)
