import json
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.user import User

def log_audit_event(
    db: Session,
    action: str,
    user: Optional[User] = None,
    details: Optional[Any] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """Record a security/audit event into the database, scrubbing sensitive info first."""
    details_str = None
    if details is not None:
        if isinstance(details, (dict, list)):
            scrubbed = scrub_sensitive_keys(details)
            details_str = json.dumps(scrubbed)
        else:
            details_str = str(details)

    db_log = AuditLog(
        user_id=user.id if user else None,
        username=user.username or user.email if user else "SYSTEM",
        action=action,
        details=details_str,
        ip_address=ip_address
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def scrub_sensitive_keys(data: Any) -> Any:
    """Recursively scrub sensitive keys like passwords, tokens, secrets, or SNMP communities."""
    if isinstance(data, dict):
        scrubbed = {}
        for k, v in data.items():
            k_lower = k.lower()
            if any(secret_word in k_lower for secret_word in ["password", "token", "secret", "community", "key"]):
                scrubbed[k] = "********"
            else:
                scrubbed[k] = scrub_sensitive_keys(v)
        return scrubbed
    elif isinstance(data, list):
        return [scrub_sensitive_keys(item) for item in data]
    return data
