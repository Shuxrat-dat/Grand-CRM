from .models import CenterSettings
from django.conf import settings


def crm_context(request):
    """
    Global CRM context processor for templates.
    """
    is_owner = False
    is_admin = False
    if request.user.is_authenticated:
        is_owner = request.user.is_owner
        is_admin = request.user.is_admin_staff

    try:
        center_settings = CenterSettings.get_settings()
    except Exception:
        center_settings = None

    return {
        'is_owner': is_owner,
        'is_admin': is_admin,
        'center_settings': center_settings,
        'CURRENCY_CODE': getattr(settings, 'CURRENCY_CODE', 'UZS'),
        'CURRENCY_SYMBOL': getattr(settings, 'CURRENCY_SYMBOL', "so'm"),
    }
