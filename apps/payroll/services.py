from decimal import Decimal
from datetime import date, datetime
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.audit.services import log_audit
from apps.academics.models import Teacher
from .models import SalaryRecord, SalaryPayment


@transaction.atomic
def generate_monthly_salary(teacher_id: int, period_month: date, user=None, custom_amount: Decimal = None) -> SalaryRecord:
    """
    Generates monthly salary accrual for a teacher based on their active TeacherSalaryRate on that date.
    """
    teacher = Teacher.objects.select_for_update().get(id=teacher_id)
    period_month_first = date(period_month.year, period_month.month, 1)

    existing = SalaryRecord.objects.filter(
        teacher=teacher,
        period_month=period_month_first
    ).first()

    if existing and existing.status != SalaryRecord.Status.CANCELLED:
        raise ValidationError(f"{teacher.full_name} uchun {period_month_first.strftime('%Y-%m')} oylik maoshi allaqachon hisoblangan.")

    if custom_amount is not None:
        amount = Decimal(str(custom_amount))
    else:
        active_rate = teacher.get_salary_rate_for_date(period_month_first)
        if not active_rate:
            raise ValidationError(f"{teacher.full_name} uchun {period_month_first.strftime('%Y-%m')} sanasiga maosh stavkasi belgilanmagan.")
        amount = active_rate.monthly_amount

    salary = SalaryRecord.objects.create(
        teacher=teacher,
        period_month=period_month_first,
        amount=amount,
        status=SalaryRecord.Status.PENDING
    )

    log_audit(
        actor=user,
        action='SALARY',
        entity_type='SalaryRecord',
        entity_id=salary.id,
        changes_after={
            'teacher': teacher.full_name,
            'amount': str(amount),
            'period_month': period_month_first.isoformat(),
            'status': salary.status
        },
        reason=f"{period_month_first.strftime('%Y-%m')} oylik maosh hisoblandi"
    )

    return salary


@transaction.atomic
def approve_salary(salary_id: int, user) -> SalaryRecord:
    """
    Approves a salary record so payments can be issued against it.
    """
    salary = SalaryRecord.objects.select_for_update().get(id=salary_id)
    if salary.status not in [SalaryRecord.Status.PENDING, SalaryRecord.Status.PARTIAL]:
        raise ValidationError("Faqat kutilayotgan yoki qisman to'langan oylikni tasdiqlash mumkin.")

    salary.status = SalaryRecord.Status.APPROVED
    salary.approved_by = user
    salary.approved_at = timezone.now()
    salary.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    log_audit(
        actor=user,
        action='APPROVE',
        entity_type='SalaryRecord',
        entity_id=salary.id,
        changes_after={'status': 'approved'},
        reason="Oylik maosh egasi tomonidan tasdiqlandi"
    )

    return salary


@transaction.atomic
def register_salary_payment(
    salary_id: int,
    amount: Decimal,
    method: str,
    paid_at: datetime = None,
    reference: str = "",
    user = None,
    allow_overpay: bool = False
) -> SalaryPayment:
    """
    Disburses a salary payment. Ensures payments do not exceed remaining salary obligation
    unless explicitly allowed.
    """
    if amount <= Decimal('0.00'):
        raise ValidationError("To'lov summasi 0 dan katta bo'lishi shart.")

    salary = SalaryRecord.objects.select_for_update().get(id=salary_id)

    if salary.status == SalaryRecord.Status.CANCELLED:
        raise ValidationError("Bekor qilingan oylik bo'yicha to'lov amalga oshirib bo'lmaydi.")

    # Auto-approve if owner makes payment directly
    if salary.status == SalaryRecord.Status.PENDING:
        salary.status = SalaryRecord.Status.APPROVED
        salary.approved_by = user
        salary.approved_at = timezone.now()
        salary.save(update_fields=['status', 'approved_by', 'approved_at'])

    rem = salary.remaining_balance
    if not allow_overpay and amount > rem:
        raise ValidationError(
            f"To'lov summasi qolgan oylik qarzidan ({rem} so'm) oshib ketdi. Ruxsatsiz ortiqcha to'lab bo'lmaydi."
        )

    if not paid_at:
        paid_at = timezone.now()

    payment = SalaryPayment.objects.create(
        salary_record=salary,
        amount=amount,
        paid_at=paid_at,
        method=method,
        reference=reference,
        status=SalaryPayment.Status.COMPLETED,
        created_by=user
    )

    salary.refresh_status()

    log_audit(
        actor=user,
        action='SALARY',
        entity_type='SalaryPayment',
        entity_id=payment.id,
        changes_after={
            'teacher': salary.teacher.full_name,
            'amount': str(amount),
            'method': method,
            'remaining': str(salary.remaining_balance)
        },
        reason="Ish haqi to'lab berildi"
    )

    return payment


@transaction.atomic
def cancel_salary_payment(payment_id: int, user, reason: str) -> SalaryPayment:
    """
    Cancels a salary payment (Storno).
    """
    if not reason:
        raise ValidationError("Bekor qilish sababi ko'rsatilishi shart.")

    payment = SalaryPayment.objects.select_for_update().get(id=payment_id)
    if payment.status == SalaryPayment.Status.CANCELLED:
        raise ValidationError("Ushbu ish haqi to'lovi allaqachon bekor qilingan.")

    payment.status = SalaryPayment.Status.CANCELLED
    payment.cancellation_reason = reason
    payment.cancelled_at = timezone.now()
    payment.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])

    salary = payment.salary_record
    salary.refresh_status()

    log_audit(
        actor=user,
        action='CANCEL',
        entity_type='SalaryPayment',
        entity_id=payment.id,
        changes_after={'status': 'cancelled', 'reason': reason},
        reason=f"Ish haqi to'lovi bekor qilindi: {reason}"
    )

    return payment


@transaction.atomic
def cancel_salary_record(salary_id: int, user, reason: str) -> SalaryRecord:
    """
    Cancels a salary record. Requires that no completed payments remain.
    """
    if not reason:
        raise ValidationError("Sabab ko'rsatilishi shart.")

    salary = SalaryRecord.objects.select_for_update().get(id=salary_id)
    if salary.status == SalaryRecord.Status.CANCELLED:
        raise ValidationError("Ushbu maosh hisobi allaqachon bekor qilingan.")

    completed_payments_count = salary.payments.filter(status=SalaryPayment.Status.COMPLETED).count()
    if completed_payments_count > 0:
        raise ValidationError("Bu hisob bo'yicha to'langan to'lovlar mavjud. Avval ularni bekor qiling.")

    salary.status = SalaryRecord.Status.CANCELLED
    salary.notes = f"{salary.notes}\n[Bekor qilindi]: {reason}".strip()
    salary.save(update_fields=['status', 'notes', 'updated_at'])

    log_audit(
        actor=user,
        action='CANCEL',
        entity_type='SalaryRecord',
        entity_id=salary.id,
        changes_after={'status': 'cancelled', 'reason': reason},
        reason=f"Maosh hisobi bekor qilindi: {reason}"
    )

    return salary
