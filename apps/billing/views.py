from datetime import date
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.decorators import admin_or_owner_required
from apps.accounts.models import CenterSettings
from .models import MonthlyCharge, Payment, PaymentAllocation
from .forms import PaymentForm, MonthlyChargeForm, BulkChargesForm, CancelReasonForm
from .services import (
    register_payment, cancel_payment, generate_monthly_charge,
    cancel_charge, update_all_charge_statuses
)
from apps.students.models import Student
from apps.academics.models import Enrollment, StudyGroup


# --- CHARGES ---

@admin_or_owner_required
def charges_list_view(request):
    update_all_charge_statuses()

    status_filter = request.GET.get('status', '')
    month_filter = request.GET.get('month', '')
    group_id = request.GET.get('group', '')

    charges = MonthlyCharge.objects.select_related(
        'student', 'enrollment', 'enrollment__group', 'enrollment__group__course'
    ).prefetch_related('allocations').order_by('-billing_month', '-created_at')

    if status_filter:
        charges = charges.filter(status=status_filter)
    if month_filter:
        try:
            y, m = month_filter.split('-')
            charges = charges.filter(billing_month__year=int(y), billing_month__month=int(m))
        except Exception:
            pass
    if group_id:
        charges = charges.filter(enrollment__group_id=group_id)

    groups = StudyGroup.objects.filter(is_active=True).order_by('name')

    return render(request, 'billing/charges_list.html', {
        'charges': charges[:100],
        'groups': groups,
        'status_filter': status_filter,
        'month_filter': month_filter,
        'selected_group': group_id,
        'status_choices': MonthlyCharge.Status.choices,
    })


@admin_or_owner_required
def charge_create_view(request):
    settings_obj = CenterSettings.get_settings()
    initial = {
        'billing_month': date(timezone.now().year, timezone.now().month, 1),
        'proration_policy': settings_obj.proration_policy
    }

    if request.method == 'POST':
        form = MonthlyChargeForm(request.POST)
        if form.is_valid():
            enrollment = form.cleaned_data['enrollment']
            billing_month = form.cleaned_data['billing_month']
            policy = form.cleaned_data['proration_policy']
            custom_amount = form.cleaned_data.get('custom_amount')
            due_date = form.cleaned_data.get('due_date')

            try:
                charge = generate_monthly_charge(
                    enrollment_id=enrollment.id,
                    billing_month=billing_month,
                    proration_policy=policy,
                    user=request.user,
                    custom_amount=custom_amount,
                    due_date=due_date
                )
                messages.success(request, f"{charge.student.full_name} uchun {charge.billing_month.strftime('%Y-%m')} oylik hisob shakllantirildi.")
                return redirect('billing:charges_list')
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
    else:
        form = MonthlyChargeForm(initial=initial)

    return render(request, 'billing/charge_form.html', {'form': form, 'title': "Oylik hisob shakllantirish"})


@admin_or_owner_required
def generate_bulk_charges_view(request):
    settings_obj = CenterSettings.get_settings()
    initial = {
        'billing_month': date(timezone.now().year, timezone.now().month, 1),
        'proration_policy': settings_obj.proration_policy
    }

    if request.method == 'POST':
        form = BulkChargesForm(request.POST)
        if form.is_valid():
            group = form.cleaned_data.get('group')
            billing_month = form.cleaned_data['billing_month']
            policy = form.cleaned_data['proration_policy']

            enrollments = Enrollment.objects.filter(status=Enrollment.Status.ACTIVE)
            if group:
                enrollments = enrollments.filter(group=group)

            created_count = 0
            skipped_count = 0

            for enrollment in enrollments:
                try:
                    generate_monthly_charge(
                        enrollment_id=enrollment.id,
                        billing_month=billing_month,
                        proration_policy=policy,
                        user=request.user
                    )
                    created_count += 1
                except ValidationError:
                    skipped_count += 1

            messages.success(
                request,
                f"Ommaviy hisoblash yakunlandi: {created_count} ta yangi hisob yaratildi, {skipped_count} ta avvaldan mavjud hisoblar o'tkazib yuborildi."
            )
            return redirect('billing:charges_list')
    else:
        form = BulkChargesForm(initial=initial)

    return render(request, 'billing/bulk_charges_form.html', {'form': form, 'title': "Ommaviy oylik hisoblash"})


@admin_or_owner_required
def charge_cancel_view(request, charge_id):
    charge = get_object_or_404(MonthlyCharge, id=charge_id)

    if request.method == 'POST':
        form = CancelReasonForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            try:
                cancel_charge(charge_id=charge.id, user=request.user, reason=reason)
                messages.warning(request, f"Hisob #{charge.id} bekor qilindi.")
                return redirect('billing:charges_list')
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = CancelReasonForm()

    return render(request, 'billing/confirm_cancel.html', {
        'form': form,
        'title': f"Hisobni bekor qilish: #{charge.id} - {charge.student.full_name}",
        'charge': charge
    })


# --- PAYMENTS ---

@admin_or_owner_required
def payments_list_view(request):
    student_id = request.GET.get('student', '')
    method_filter = request.GET.get('method', '')
    status_filter = request.GET.get('status', '')

    payments = Payment.objects.select_related('student', 'created_by').prefetch_related('allocations__charge')

    if student_id:
        payments = payments.filter(student_id=student_id)
    if method_filter:
        payments = payments.filter(method=method_filter)
    if status_filter:
        payments = payments.filter(status=status_filter)

    return render(request, 'billing/payments_list.html', {
        'payments': payments.order_by('-paid_at')[:100],
        'method_filter': method_filter,
        'status_filter': status_filter,
        'method_choices': Payment.Method.choices,
        'status_choices': Payment.Status.choices,
    })


@admin_or_owner_required
def payment_create_view(request, student_id=None):
    if request.method == 'POST':
        form = PaymentForm(request.POST, student_id=student_id)
        if form.is_valid():
            student = form.cleaned_data['student']
            amount = form.cleaned_data['amount']
            method = form.cleaned_data['method']
            paid_at = form.cleaned_data['paid_at']
            reference = form.cleaned_data['reference']
            idempotency_key = form.cleaned_data['idempotency_key']
            target_charge = form.cleaned_data.get('charge')

            try:
                payment = register_payment(
                    student_id=student.id,
                    amount=amount,
                    method=method,
                    paid_at=paid_at,
                    reference=reference,
                    user=request.user,
                    idempotency_key=idempotency_key,
                    charge_id=target_charge.id if target_charge else None
                )
                messages.success(request, f"{student.full_name} dan {amount} so'm to'lov muvaffaqiyatli qabul qilindi.")
                return redirect('billing:payment_detail', payment_id=payment.id)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = PaymentForm(student_id=student_id)

    return render(request, 'billing/payment_form.html', {
        'form': form,
        'title': "To'lov qabul qilish",
        'student_id': student_id
    })


@admin_or_owner_required
def payment_detail_view(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related('student', 'created_by').prefetch_related(
            'allocations__charge__enrollment__group'
        ),
        id=payment_id
    )
    allocations = payment.allocations.all()

    return render(request, 'billing/payment_detail.html', {
        'payment': payment,
        'allocations': allocations,
    })


@admin_or_owner_required
def payment_cancel_view(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)

    if request.method == 'POST':
        form = CancelReasonForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            try:
                cancel_payment(payment_id=payment.id, user=request.user, reason=reason)
                messages.warning(request, f"To'lov #{payment.id} bekor qilindi (storno).")
                return redirect('billing:payments_list')
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = CancelReasonForm()

    return render(request, 'billing/confirm_cancel.html', {
        'form': form,
        'title': f"To'lovni bekor qilish (Storno): #{payment.id} - {payment.student.full_name}",
        'payment': payment
    })


# --- DEBTORS ---

@admin_or_owner_required
def debtors_list_view(request):
    update_all_charge_statuses()

    from apps.reporting.services import get_debtors_report
    debtors = get_debtors_report()

    total_system_debt = sum([d['total_debt'] for d in debtors], Decimal('0.00'))

    return render(request, 'billing/debtors_list.html', {
        'debtors': debtors,
        'total_system_debt': total_system_debt,
    })
