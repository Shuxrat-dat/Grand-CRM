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

    new_leads_count = 0
    due_leads = []
    due_leads_count = 0
    if request.user.is_authenticated:
        try:
            from django.utils import timezone
            from apps.leads.models import Lead
            new_leads_count = Lead.objects.filter(status=Lead.Status.YANGI).count()
            due_qs = Lead.objects.filter(
                next_contact_at__isnull=False,
                next_contact_at__lte=timezone.now(),
            ).exclude(status__in=[Lead.Status.CONVERTED, Lead.Status.RAD_ETDI]).order_by('next_contact_at')
            due_leads_count = due_qs.count()
            due_leads = list(due_qs[:5])
        except Exception:
            new_leads_count = 0
            due_leads = []
            due_leads_count = 0

    return {
        'is_owner': is_owner,
        'is_admin': is_admin,
        'center_settings': center_settings,
        'new_leads_count': new_leads_count,
        'due_leads': due_leads,
        'due_leads_count': due_leads_count,
        'CURRENCY_CODE': getattr(settings, 'CURRENCY_CODE', 'UZS'),
        'CURRENCY_SYMBOL': getattr(settings, 'CURRENCY_SYMBOL', "so'm"),
    }
