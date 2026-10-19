import calendar
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.models import CenterSettings
from apps.audit.services import log_audit
from .models import MonthlyCharge, Payment, PaymentAllocation
from apps.students.models import Student
from apps.academics.models import Enrollment


def calculate_charge_amount(enrollment: Enrollment, billing_month: date, policy: str = None) -> Decimal:
    """
    Calculates monthly charge amount based on proration policy:
    - FULL_MONTH: returns full enrollment monthly_price
    - PROPORTIONAL: calculates proportion of active days in the month
    """
    monthly_price = enrollment.monthly_price
    year = billing_month.year
    month = billing_month.month
    _, total_days = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, total_days)

    if not policy:
        settings_obj = CenterSettings.get_settings()
        policy = settings_obj.proration_policy

    if policy == CenterSettings.ProrationPolicy.FULL_MONTH:
        return monthly_price

    # Proportional calculation
    active_start = max(month_start, enrollment.start_date)
    active_end = min(month_end, enrollment.end_date) if enrollment.end_date else month_end

    if active_start > month_end or active_end < month_start or active_start > active_end:
        return Decimal('0.00')

    active_days = (active_end - active_start).days + 1
    if active_days >= total_days:
        return monthly_price

    daily_rate = monthly_price / Decimal(total_days)
    prorated = (daily_rate * Decimal(active_days)).quantize(Decimal('1.00'), rounding=ROUND_HALF_UP)
    return prorated


@transaction.atomic
def generate_monthly_charge(enrollment_id: int, billing_month: date, proration_policy: str = None, user=None, custom_amount: Decimal = None, due_date: date = None) -> MonthlyCharge:
    """
    Generates a monthly charge for a given enrollment and billing month.
    Avoids duplicate charges via UniqueConstraint.
    Automatically applies any existing unallocated prepayments for the student.
    """
    enrollment = Enrollment.objects.select_for_update().get(id=enrollment_id)
    student = enrollment.student
    
    # Ensure billing_month is first day of month
    billing_month_first = date(billing_month.year, billing_month.month, 1)

    existing = MonthlyCharge.objects.filter(
        student=student,
        enrollment=enrollment,
        billing_month=billing_month_first
    ).first()

    if existing and existing.status != MonthlyCharge.Status.CANCELLED:
        raise ValidationError(f"{student.full_name} uchun {billing_month_first.strftime('%Y-%m')} oyiga hisob allaqachon mavjud.")

    if custom_amount is not None:
        amount = Decimal(str(custom_amount))
    else:
        amount = calculate_charge_amount(enrollment, billing_month_first, proration_policy)

    if not due_date:
        settings_obj = CenterSettings.get_settings()
        day = min(settings_obj.payment_due_day, calendar.monthrange(billing_month_first.year, billing_month_first.month)[1])
        due_date = date(billing_month_first.year, billing_month_first.month, day)

    charge = MonthlyCharge.objects.create(
        student=student,
        enrollment=enrollment,
        billing_month=billing_month_first,
        amount=amount,
        due_date=due_date,
        status=MonthlyCharge.Status.UNPAID
    )

    # Automatically allocate available unallocated prepayments from earlier completed payments
    allocate_student_prepayments_to_charge(charge)
    charge.refresh_status()

    log_audit(
        actor=user,
        action='CREATE',
        entity_type='MonthlyCharge',
        entity_id=charge.id,
        changes_after={
            'student': student.full_name,
            'amount': str(amount),
            'billing_month': billing_month_first.isoformat(),
            'due_date': due_date.isoformat(),
            'status': charge.status
        },
        reason=f"{billing_month_first.strftime('%Y-%m')} oylik hisob shakllantirildi"
    )

    return charge


def allocate_student_prepayments_to_charge(charge: MonthlyCharge):
    """
    Finds completed payments of the student that have unallocated amounts and allocates them to this charge.
    """
    if charge.status in [MonthlyCharge.Status.PAID, MonthlyCharge.Status.CANCELLED]:
        return

    rem_needed = charge.remaining_balance
    if rem_needed <= Decimal('0.00'):
        return

    # Find payments with available balance
    payments = Payment.objects.filter(
        student=charge.student,
        status=Payment.Status.COMPLETED
    ).order_by('paid_at')

    for payment in payments:
        unalloc = payment.unallocated_amount
        if unalloc > Decimal('0.00'):
            alloc_amt = min(rem_needed, unalloc)
            PaymentAllocation.objects.create(
                payment=payment,
                charge=charge,
                amount=alloc_amt
            )
            rem_needed -= alloc_amt
            if rem_needed <= Decimal('0.00'):
                break


@transaction.atomic
def register_payment(
    student_id: int,
    amount: Decimal,
    method: str,
    paid_at: datetime = None,
    reference: str = "",
    user = None,
    idempotency_key: str = None,
    charge_id: int = None
) -> Payment:
    """
    Registers a payment with idempotency protection and atomic allocation.
    Allocates to past debts first (FIFO) or to specific charge if provided.
    Excess amount remains as prepayment for future charges.
    """
    if amount <= Decimal('0.00'):
        raise ValidationError("To'lov summasi 0 dan katta bo'lishi shart.")

    # Idempotency check
    if idempotency_key:
        existing_payment = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing_payment:
            return existing_payment

    student = Student.objects.select_for_update().get(id=student_id)

    if not paid_at:
        paid_at = timezone.now()

    payment = Payment.objects.create(
        student=student,
        amount=amount,
        paid_at=paid_at,
        method=method,
        reference=reference,
        idempotency_key=idempotency_key or None,
        status=Payment.Status.COMPLETED,
        created_by=user
    )

    remaining_payment = amount

    # 1. If specific charge requested, prioritize it
    if charge_id:
        target_charge = MonthlyCharge.objects.select_for_update().filter(
            id=charge_id,
            student=student
        ).exclude(status=MonthlyCharge.Status.CANCELLED).first()

        if target_charge and target_charge.remaining_balance > Decimal('0.00'):
            alloc_amt = min(remaining_payment, target_charge.remaining_balance)
            PaymentAllocation.objects.create(
                payment=payment,
                charge=target_charge,
                amount=alloc_amt
            )
            remaining_payment -= alloc_amt
            target_charge.refresh_status()

    # 2. Allocate remaining payment to unpaid/partial/overdue charges in FIFO order (oldest first)
    if remaining_payment > Decimal('0.00'):
        unpaid_charges = MonthlyCharge.objects.select_for_update().filter(
            student=student
        ).exclude(
            status__in=[MonthlyCharge.Status.PAID, MonthlyCharge.Status.CANCELLED]
        ).order_by('billing_month', 'created_at')

        for charge in unpaid_charges:
            needed = charge.remaining_balance
            if needed > Decimal('0.00'):
                alloc_amt = min(remaining_payment, needed)
                PaymentAllocation.objects.create(
                    payment=payment,
                    charge=charge,
                    amount=alloc_amt
                )
                remaining_payment -= alloc_amt
                charge.refresh_status()

            if remaining_payment <= Decimal('0.00'):
                break

    log_audit(
        actor=user,
        action='PAYMENT',
        entity_type='Payment',
        entity_id=payment.id,
        changes_after={
            'student': student.full_name,
            'amount': str(amount),
            'method': method,
            'reference': reference,
            'unallocated': str(payment.unallocated_amount)
        },
        reason="To'lov qabul qilindi va taqsimlandi"
    )

    return payment


@transaction.atomic
def cancel_payment(payment_id: int, user, reason: str) -> Payment:
    """
    Cancels a payment (Storno), removing its allocations and recalculating charge statuses.
    """
    if not reason:
        raise ValidationError("Bekor qilish sababi ko'rsatilishi shart.")

    payment = Payment.objects.select_for_update().get(id=payment_id)

    if payment.status == Payment.Status.CANCELLED:
        raise ValidationError("Ushbu to'lov allaqachon bekor qilingan.")

    # Record which charges had allocations
    allocations = list(payment.allocations.select_related('charge').all())
    affected_charges = [alloc.charge for alloc in allocations]

    payment.status = Payment.Status.CANCELLED
    payment.cancellation_reason = reason
    payment.cancelled_at = timezone.now()
    payment.save(update_fields=['status', 'cancellation_reason', 'cancelled_at'])

    # Delete allocations for cancelled payment so charges become unpaid/partial again
    payment.allocations.all().delete()

    for charge in affected_charges:
        charge.refresh_status()
        # Try to reallocate any other available prepayments if any exist
        allocate_student_prepayments_to_charge(charge)
        charge.refresh_status()

    log_audit(
        actor=user,
        action='CANCEL',
        entity_type='Payment',
        entity_id=payment.id,
        changes_after={'status': 'cancelled', 'reason': reason},
        reason=f"To'lov bekor qilindi (storno): {reason}"
    )

    return payment


@transaction.atomic
def cancel_charge(charge_id: int, user, reason: str) -> MonthlyCharge:
    """
    Cancels a monthly charge, releasing any payment allocations so they can cover other charges or remain as prepayments.
    """
    if not reason:
        raise ValidationError("Hisobni bekor qilish sababi ko'rsatilishi shart.")

    charge = MonthlyCharge.objects.select_for_update().get(id=charge_id)

    if charge.status == MonthlyCharge.Status.CANCELLED:
        raise ValidationError("Ushbu hisob allaqachon bekor qilingan.")

    # Delete existing allocations so payments are freed up
    allocations = list(charge.allocations.select_related('payment').all())
    affected_payments = [alloc.payment for alloc in allocations]
    charge.allocations.all().delete()

    charge.status = MonthlyCharge.Status.CANCELLED
    charge.notes = f"{charge.notes}\n[Bekor qilindi]: {reason}".strip()
    charge.save(update_fields=['status', 'notes', 'updated_at'])

    # Reallocate freed payment amounts to other unpaid charges of the student
    for p in affected_payments:
        if p.status == Payment.Status.COMPLETED and p.unallocated_amount > Decimal('0.00'):
            # Find next unpaid charge
            other_charges = MonthlyCharge.objects.select_for_update().filter(
                student=charge.student
            ).exclude(
                status__in=[MonthlyCharge.Status.PAID, MonthlyCharge.Status.CANCELLED]
            ).order_by('billing_month')

            rem_p = p.unallocated_amount
            for other in other_charges:
                needed = other.remaining_balance
                if needed > Decimal('0.00'):
                    amt = min(rem_p, needed)
                    PaymentAllocation.objects.create(payment=p, charge=other, amount=amt)
                    rem_p -= amt
                    other.refresh_status()
                if rem_p <= Decimal('0.00'):
                    break

    log_audit(
        actor=user,
        action='CANCEL',
        entity_type='MonthlyCharge',
        entity_id=charge.id,
        changes_after={'status': 'cancelled', 'reason': reason},
        reason=f"Hisob bekor qilindi: {reason}"
    )

    return charge


def update_all_charge_statuses(target_date: date = None):
    """
    Refreshes statuses of all unpaid/partial charges according to target_date.
    Marks past due date charges as OVERDUE.
    """
    if not target_date:
        target_date = timezone.now().date()

    charges = MonthlyCharge.objects.exclude(status__in=[MonthlyCharge.Status.PAID, MonthlyCharge.Status.CANCELLED])
    for c in charges:
        c.refresh_status()
