"""
Email Service Compatibility Module.
Delegates to app.services.email_service for centralized email operations.
"""
from app.services.email_service import EmailService, send_password_reset_email, latest_dev_email

__all__ = ["EmailService", "send_password_reset_email", "latest_dev_email"]
