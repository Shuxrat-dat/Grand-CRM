from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.decorators import owner_required
from .models import SalaryRecord, SalaryPayment
from .forms import SalaryGenerateForm, BulkSalaryGenerateForm, SalaryPaymentForm
from apps.billing.forms import CancelReasonForm
from .services import (
    generate_monthly_salary, approve_salary, register_salary_payment,
    cancel_salary_payment, cancel_salary_record
)
from apps.academics.models import Teacher


@owner_required
def salaries_list_view(request):
    month_filter = request.GET.get('month', '')
    status_filter = request.GET.get('status', '')
    teacher_id = request.GET.get('teacher', '')

    salaries = SalaryRecord.objects.select_related('teacher', 'approved_by').prefetch_related('payments').order_by('-period_month')

    if month_filter:
        try:
            y, m = month_filter.split('-')
            salaries = salaries.filter(period_month__year=int(y), period_month__month=int(m))
        except Exception:
            pass
    if status_filter:
        salaries = salaries.filter(status=status_filter)
    if teacher_id:
        salaries = salaries.filter(teacher_id=teacher_id)

    teachers = Teacher.objects.all().order_by('full_name')

    return render(request, 'payroll/salaries_list.html', {
        'salaries': salaries[:100],
        'teachers': teachers,
        'month_filter': month_filter,
        'status_filter': status_filter,
        'selected_teacher': teacher_id,
        'status_choices': SalaryRecord.Status.choices,
    })


@owner_required
def salary_generate_view(request):
    initial = {'period_month': date(timezone.now().year, timezone.now().month, 1)}

    if request.method == 'POST':
        form = SalaryGenerateForm(request.POST)
        if form.is_valid():
            teacher = form.cleaned_data['teacher']
            period_month = form.cleaned_data['period_month']
            custom_amount = form.cleaned_data.get('custom_amount')

            try:
                salary = generate_monthly_salary(
                    teacher_id=teacher.id,
                    period_month=period_month,
                    user=request.user,
                    custom_amount=custom_amount
                )
                messages.success(request, f"{teacher.full_name} uchun {salary.period_month.strftime('%Y-%m')} oylik maoshi hisoblandi.")
                return redirect('payroll:salaries_list')
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = SalaryGenerateForm(initial=initial)

    return render(request, 'payroll/salary_form.html', {'form': form, 'title': "Oylik maosh hisoblash"})


@owner_required
def salary_bulk_generate_view(request):
    initial = {'period_month': date(timezone.now().year, timezone.now().month, 1)}

    if request.method == 'POST':
        form = BulkSalaryGenerateForm(request.POST)
        if form.is_valid():
            period_month = form.cleaned_data['period_month']
            teachers = Teacher.objects.filter(status=Teacher.Status.ACTIVE)

            created_count = 0
            skipped_count = 0

            for teacher in teachers:
                try:
                    generate_monthly_salary(
                        teacher_id=teacher.id,
                        period_month=period_month,
                        user=request.user
                    )
                    created_count += 1
                except ValidationError:
                    skipped_count += 1

            messages.success(
                request,
                f"Ommaviy ish haqi hisoblash: {created_count} ta yangi hisoblandi, {skipped_count} ta o'qituvchi o'tkazib yuborildi."
            )
            return redirect('payroll:salaries_list')
    else:
        form = BulkSalaryGenerateForm(initial=initial)

    return render(request, 'payroll/bulk_salary_form.html', {'form': form, 'title': "Ommaviy maosh hisoblash"})


@owner_required
def salary_approve_view(request, salary_id):
    if request.method == 'POST':
        try:
            approve_salary(salary_id=salary_id, user=request.user)
            messages.success(request, "Oylik maosh tasdiqlandi. Endi to'lovlarni amalga oshirish mumkin.")
        except ValidationError as e:
            messages.error(request, str(e))
    return redirect('payroll:salaries_list')


@owner_required
def salary_payment_create_view(request, salary_id):
    salary = get_object_or_404(SalaryRecord.objects.select_related('teacher'), id=salary_id)

    if request.method == 'POST':
        form = SalaryPaymentForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            method = form.cleaned_data['method']
            paid_at = form.cleaned_data['paid_at']
            reference = form.cleaned_data['reference']
            allow_overpay = form.cleaned_data.get('allow_overpay', False)

            try:
                payment = register_salary_payment(
                    salary_id=salary.id,
                    amount=amount,
                    method=method,
                    paid_at=paid_at,
                    reference=reference,
                    user=request.user,
                    allow_overpay=allow_overpay
                )
                messages.success(request, f"{salary.teacher.full_name} ga {amount} so'm ish haqi to'lab berildi.")
                return redirect('payroll:salaries_list')
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        initial = {'amount': salary.remaining_balance}
        form = SalaryPaymentForm(initial=initial)

    return render(request, 'payroll/salary_payment_form.html', {
        'form': form,
        'salary': salary,
        'title': f"Ish haqi to'lash: {salary.teacher.full_name} ({salary.period_month.strftime('%Y-%m')})"
    })


@owner_required
def salary_payment_cancel_view(request, payment_id):
    payment = get_object_or_404(SalaryPayment, id=payment_id)

    if request.method == 'POST':
        form = CancelReasonForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            try:
                cancel_salary_payment(payment_id=payment.id, user=request.user, reason=reason)
                messages.warning(request, f"Ish haqi to'lovi #{payment.id} bekor qilindi.")
                return redirect('payroll:salaries_list')
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = CancelReasonForm()

    return render(request, 'payroll/confirm_cancel.html', {
        'form': form,
        'title': f"Ish haqi to'lovini bekor qilish: #{payment.id} - {payment.salary_record.teacher.full_name}",
        'payment': payment
    })


@owner_required
def salary_cancel_view(request, salary_id):
    salary = get_object_or_404(SalaryRecord, id=salary_id)

    if request.method == 'POST':
        form = CancelReasonForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            try:
                cancel_salary_record(salary_id=salary.id, user=request.user, reason=reason)
                messages.warning(request, f"Maosh hisobi #{salary.id} bekor qilindi.")
                return redirect('payroll:salaries_list')
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = CancelReasonForm()

    return render(request, 'payroll/confirm_cancel.html', {
        'form': form,
        'title': f"Maosh hisobini bekor qilish: #{salary.id} - {salary.teacher.full_name}",
        'salary': salary
    })
