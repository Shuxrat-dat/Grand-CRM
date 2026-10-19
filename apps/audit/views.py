from django.shortcuts import render
from apps.accounts.decorators import owner_required
from .models import AuditLog


@owner_required
def audit_logs_list_view(request):
    action_filter = request.GET.get('action', '')
    entity_filter = request.GET.get('entity_type', '')
    q = request.GET.get('q', '').strip()

    logs = AuditLog.objects.select_related('actor').order_by('-timestamp')

    if action_filter:
        logs = logs.filter(action=action_filter)
    if entity_filter:
        logs = logs.filter(entity_type=entity_filter)
    if q:
        logs = logs.filter(reason__icontains=q)

    return render(request, 'audit/audit_logs_list.html', {
        'logs': logs[:200],
        'action_filter': action_filter,
        'entity_filter': entity_filter,
        'q': q,
        'action_choices': AuditLog.Action.choices,
    })
