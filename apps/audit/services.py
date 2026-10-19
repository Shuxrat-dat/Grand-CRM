import json
from decimal import Decimal
from datetime import date, datetime
from .models import AuditLog


SENSITIVE_KEYS = {'password', 'token', 'secret', 'key', 'csrfmiddlewaretoken', 'access_token', 'refresh_token'}


def _serialize_val(val):
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    return val


def sanitize_dict(data):
    if not isinstance(data, dict):
        return {}
    clean = {}
    for k, v in data.items():
        if any(sensitive in k.lower() for sensitive in SENSITIVE_KEYS):
            clean[k] = '***REDACTED***'
        elif isinstance(v, dict):
            clean[k] = sanitize_dict(v)
        elif isinstance(v, list):
            clean[k] = [_serialize_val(x) for x in v]
        else:
            clean[k] = _serialize_val(v)
    return clean


def log_audit(actor, action, entity_type, entity_id, changes_before=None, changes_after=None, reason="", ip_address=None):
    """
    Central helper to record audit logs.
    """
    try:
        AuditLog.objects.create(
            actor=actor if actor and getattr(actor, 'is_authenticated', False) else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            changes_before=sanitize_dict(changes_before) if changes_before else {},
            changes_after=sanitize_dict(changes_after) if changes_after else {},
            reason=reason or "",
            ip_address=ip_address
        )
    except Exception as e:
        # Never break main transaction because of audit log failure, but log if needed
        pass
