from decimal import Decimal
from datetime import date
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.audit.services import log_audit
from .models import Expense


@transaction.atomic
def create_expense(
    category: str,
    amount: Decimal,
    occurred_at: date,
    description: str,
    method: str = Expense.Method.CASH,
    user = None
) -> Expense:
    """
    Creates an operational expense. Accessible only by Owner.
    """
    if amount <= Decimal('0.00'):
        raise ValidationError("Xarajat summasi 0 dan katta bo'lishi shart.")
    if not description:
        raise ValidationError("Xarajat tavsifi ko'rsatilishi shart.")

    expense = Expense.objects.create(
        category=category,
        amount=amount,
        occurred_at=occurred_at or timezone.now().date(),
        description=description,
        method=method,
        status=Expense.Status.ACTIVE,
        created_by=user
    )

    log_audit(
        actor=user,
        action='CREATE',
        entity_type='Expense',
        entity_id=expense.id,
        changes_after={
            'category': expense.get_category_display(),
            'amount': str(amount),
            'occurred_at': expense.occurred_at.isoformat(),
            'description': description
        },
        reason="Yangi xarajat kiritildi"
    )

    return expense


@transaction.atomic
def cancel_expense(expense_id: int, user, reason: str) -> Expense:
    """
    Cancels an expense (preserves original record with reason).
    """
    if not reason:
        raise ValidationError("Bekor qilish sababi ko'rsatilishi shart.")

    expense = Expense.objects.select_for_update().get(id=expense_id)
    if expense.status == Expense.Status.CANCELLED:
        raise ValidationError("Ushbu xarajat allaqachon bekor qilingan.")

    expense.status = Expense.Status.CANCELLED
    expense.cancellation_reason = reason
    expense.cancelled_at = timezone.now()
    expense.save(update_fields=['status', 'cancellation_reason', 'cancelled_at', 'updated_at'])

    log_audit(
        actor=user,
        action='CANCEL',
        entity_type='Expense',
        entity_id=expense.id,
        changes_after={'status': 'cancelled', 'reason': reason},
        reason=f"Xarajat bekor qilindi: {reason}"
    )

    return expense
