from decimal import Decimal
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='uzs')
def uzs_currency(value):
    """
    Formats a number into Uzbek currency representation (e.g. 1 500 000 so'm).
    """
    if value is None or value == '':
        return "0 so'm"
    try:
        val = Decimal(str(value))
        # Format integer part with space separator
        formatted = f"{int(val):,}".replace(",", " ")
        return f"{formatted} so'm"
    except (ValueError, TypeError):
        return f"{value} so'm"


register.filter('format_currency', uzs_currency)



@register.filter(name='status_badge')
def status_badge(status):
    """
    Renders styled badge for various status values.
    """
    mapping = {
        'active': ('bg-success text-white', 'Faol'),
        'suspended': ('bg-warning text-dark', 'Muzlatilgan'),
        'completed': ('bg-info text-dark', 'Bitirgan / Yakunlangan'),
        'archived': ('bg-secondary text-white', 'Arxivlangan'),
        'transferred': ('bg-primary text-white', "Ko'chirilgan"),
        'dropped': ('bg-danger text-white', "To'xtatilgan"),
        'unpaid': ('bg-secondary text-white', "To'lanmagan"),
        'partial': ('bg-warning text-dark', "Qisman to'langan"),
        'paid': ('bg-success text-white', "To'langan"),
        'overdue': ('bg-danger text-white', "Muddati o'tgan"),
        'cancelled': ('bg-dark text-white', 'Bekor qilingan'),
        'pending': ('bg-warning text-dark', 'Kutilmoqda'),
        'approved': ('bg-info text-dark', 'Tasdiqlangan'),
        'present': ('bg-success text-white', 'Qatnashdi'),
        'absent': ('bg-danger text-white', 'Qatnashmadi'),
        'late': ('bg-warning text-dark', 'Kechikdi'),
        'excused': ('bg-secondary text-white', 'Sababli'),
    }
    cls, label = mapping.get(str(status).lower(), ('bg-light text-dark', str(status)))
    return mark_safe(f'<span class="badge {cls} px-2 py-1">{label}</span>')
