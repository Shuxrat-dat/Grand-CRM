import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.shortcuts import render
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q

from apps.accounts.decorators import admin_or_owner_required, owner_required
from apps.billing.models import MonthlyCharge, Payment, PaymentAllocation
from apps.payroll.models import SalaryRecord, SalaryPayment
from apps.finance.models import Expense
from apps.students.models import Student
from apps.academics.models import StudyGroup, Course, Teacher
from apps.attendance.models import Lesson, AttendanceRecord
from .services import (
    get_dashboard_metrics, get_cash_flow_report, get_accrual_profit_report,
    get_debtors_report, export_report_to_excel, export_report_to_pdf
)


def _parse_date_range(request):
    today = timezone.now().date()
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    if start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            return start_date, end_date
        except ValueError:
            pass

    # Default: first day of current month to end of current month
    start_date = date(today.year, today.month, 1)
    _, last_day = calendar.monthrange(today.year, today.month)
    end_date = date(today.year, today.month, last_day)
    return start_date, end_date


@admin_or_owner_required
def dashboard_view(request):
    start_date, end_date = _parse_date_range(request)
    is_owner = request.user.is_owner

    metrics = get_dashboard_metrics(start_date=start_date, end_date=end_date, is_owner=is_owner)

    # Chart data (last 6 months cash inflows vs outflows for Owner, or collection trends for Admin)
    today = timezone.now().date()
    chart_labels = []
    chart_inflows = []
    chart_outflows = []

    for i in range(5, -1, -1):
        # Calculate month
        target_month = today.month - i
        target_year = today.year
        while target_month <= 0:
            target_month += 12
            target_year -= 1

        _, days_in_target = calendar.monthrange(target_year, target_month)
        m_start = date(target_year, target_month, 1)
        m_end = date(target_year, target_month, days_in_target)
        label = m_start.strftime('%b %Y')
        chart_labels.append(label)

        # Inflows
        inflow = Payment.objects.filter(
            status=Payment.Status.COMPLETED,
            paid_at__date__gte=m_start,
            paid_at__date__lte=m_end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        chart_inflows.append(float(inflow))

        if is_owner:
            # Outflows (salaries + expenses)
            sal_out = SalaryPayment.objects.filter(
                status=SalaryPayment.Status.COMPLETED,
                paid_at__date__gte=m_start,
                paid_at__date__lte=m_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            exp_out = Expense.objects.filter(
                status=Expense.Status.ACTIVE,
                occurred_at__gte=m_start,
                occurred_at__lte=m_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            chart_outflows.append(float(sal_out + exp_out))

    # Owner specific: Upcoming financial due dates / deadlines
    upcoming_charges = MonthlyCharge.objects.filter(
        status__in=[MonthlyCharge.Status.UNPAID, MonthlyCharge.Status.PARTIAL],
        due_date__gte=today
    ).order_by('due_date')[:10]

    # Admin specific: Today's lessons & attention items
    today_lessons = Lesson.objects.filter(
        date=today
    ).select_related('group', 'group__course', 'group__teacher')

    debtors_attention = get_debtors_report()[:10]
    recent_payments = Payment.objects.filter(
        status=Payment.Status.COMPLETED
    ).select_related('student')[:10]

    return render(request, 'reporting/dashboard.html', {
        'metrics': metrics,
        'start_date': start_date,
        'end_date': end_date,
        'chart_labels': chart_labels,
        'chart_inflows': chart_inflows,
        'chart_outflows': chart_outflows,
        'upcoming_charges': upcoming_charges,
        'today_lessons': today_lessons,
        'debtors_attention': debtors_attention,
        'recent_payments': recent_payments,
    })


@owner_required
def report_cash_flow_view(request):
    start_date, end_date = _parse_date_range(request)
    data = get_cash_flow_report(start_date=start_date, end_date=end_date)
    return render(request, 'reporting/cash_flow.html', {'data': data, 'start_date': start_date, 'end_date': end_date})


@owner_required
def report_accrual_profit_view(request):
    start_date, end_date = _parse_date_range(request)
    data = get_accrual_profit_report(start_date=start_date, end_date=end_date)
    return render(request, 'reporting/accrual_profit.html', {'data': data, 'start_date': start_date, 'end_date': end_date})


@admin_or_owner_required
def report_payments_view(request):
    start_date, end_date = _parse_date_range(request)
    method_filter = request.GET.get('method', '')

    payments = Payment.objects.filter(
        status=Payment.Status.COMPLETED,
        paid_at__date__gte=start_date,
        paid_at__date__lte=end_date
    ).select_related('student', 'created_by')

    if method_filter:
        payments = payments.filter(method=method_filter)

    total_amount = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    return render(request, 'reporting/payments_report.html', {
        'payments': payments,
        'total_amount': total_amount,
        'start_date': start_date,
        'end_date': end_date,
        'method_filter': method_filter,
        'method_choices': Payment.Method.choices,
    })


@admin_or_owner_required
def report_charges_view(request):
    start_date, end_date = _parse_date_range(request)
    status_filter = request.GET.get('status', '')

    charges = MonthlyCharge.objects.exclude(
        status=MonthlyCharge.Status.CANCELLED
    ).filter(
        billing_month__gte=start_date,
        billing_month__lte=end_date
    ).select_related('student', 'enrollment__group')

    if status_filter:
        charges = charges.filter(status=status_filter)

    total_amount = charges.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_allocated = sum([c.allocated_amount for c in charges], Decimal('0.00'))
    total_remaining = sum([c.remaining_balance for c in charges], Decimal('0.00'))

    return render(request, 'reporting/charges_report.html', {
        'charges': charges,
        'total_amount': total_amount,
        'total_allocated': total_allocated,
        'total_remaining': total_remaining,
        'start_date': start_date,
        'end_date': end_date,
        'status_filter': status_filter,
        'status_choices': MonthlyCharge.Status.choices,
    })


@admin_or_owner_required
def report_debtors_view(request):
    debtors = get_debtors_report()
    total_debt = sum([d['total_debt'] for d in debtors], Decimal('0.00'))

    return render(request, 'reporting/debtors_report.html', {
        'debtors': debtors,
        'total_debt': total_debt,
    })


@owner_required
def report_group_revenue_view(request):
    start_date, end_date = _parse_date_range(request)

    groups = StudyGroup.objects.select_related('course', 'teacher').prefetch_related('enrollments').order_by('name')
    report_rows = []
    total_charges_sum = Decimal('0.00')
    total_collected_sum = Decimal('0.00')

    for g in groups:
        charges = MonthlyCharge.objects.exclude(status=MonthlyCharge.Status.CANCELLED).filter(
            enrollment__group=g,
            billing_month__gte=start_date,
            billing_month__lte=end_date
        )
        charged = charges.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        collected = sum([c.allocated_amount for c in charges], Decimal('0.00'))

        report_rows.append({
            'group': g,
            'active_students': g.active_students_count,
            'charged': charged,
            'collected': collected,
            'debt': max(Decimal('0.00'), charged - collected)
        })
        total_charges_sum += charged
        total_collected_sum += collected

    return render(request, 'reporting/group_revenue.html', {
        'report_rows': report_rows,
        'total_charges_sum': total_charges_sum,
        'total_collected_sum': total_collected_sum,
        'start_date': start_date,
        'end_date': end_date,
    })


@admin_or_owner_required
def report_attendance_view(request):
    start_date, end_date = _parse_date_range(request)
    group_id = request.GET.get('group', '')

    attendances = AttendanceRecord.objects.filter(
        lesson__date__gte=start_date,
        lesson__date__lte=end_date
    )

    if group_id:
        attendances = attendances.filter(lesson__group_id=group_id)

    total_records = attendances.count()
    present_count = attendances.filter(status=AttendanceRecord.Status.PRESENT).count()
    absent_count = attendances.filter(status=AttendanceRecord.Status.ABSENT).count()
    late_count = attendances.filter(status=AttendanceRecord.Status.LATE).count()
    excused_count = attendances.filter(status=AttendanceRecord.Status.EXCUSED).count()

    present_rate = round((present_count / total_records * 100), 1) if total_records > 0 else 0

    groups = StudyGroup.objects.filter(is_active=True).order_by('name')

    return render(request, 'reporting/attendance_report.html', {
        'total_records': total_records,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'excused_count': excused_count,
        'present_rate': present_rate,
        'groups': groups,
        'selected_group': group_id,
        'start_date': start_date,
        'end_date': end_date,
    })


@owner_required
def report_payroll_view(request):
    start_date, end_date = _parse_date_range(request)

    salaries = SalaryRecord.objects.exclude(
        status=SalaryRecord.Status.CANCELLED
    ).filter(
        period_month__gte=start_date,
        period_month__lte=end_date
    ).select_related('teacher')

    total_accrued = salaries.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_paid = sum([s.total_paid for s in salaries], Decimal('0.00'))
    total_remaining = sum([s.remaining_balance for s in salaries], Decimal('0.00'))

    return render(request, 'reporting/payroll_report.html', {
        'salaries': salaries,
        'total_accrued': total_accrued,
        'total_paid': total_paid,
        'total_remaining': total_remaining,
        'start_date': start_date,
        'end_date': end_date,
    })


@owner_required
def report_expenses_view(request):
    start_date, end_date = _parse_date_range(request)

    expenses = Expense.objects.filter(
        status=Expense.Status.ACTIVE,
        occurred_at__gte=start_date,
        occurred_at__lte=end_date
    ).order_by('-occurred_at')

    total_amount = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    by_category = expenses.values('category').annotate(
        total=Sum('amount'), count=Count('id')
    ).order_by('-total')

    category_labels = dict(Expense.Category.choices)
    category_summary = [
        {'name': category_labels.get(item['category'], item['category']), 'total': item['total'], 'count': item['count']}
        for item in by_category
    ]

    return render(request, 'reporting/expenses_report.html', {
        'expenses': expenses,
        'total_amount': total_amount,
        'category_summary': category_summary,
        'start_date': start_date,
        'end_date': end_date,
    })


@admin_or_owner_required
def export_report_view(request, report_type):
    """
    Exports filtered reports to Excel or PDF.
    """
    export_format = request.GET.get('format', 'excel').lower()
    start_date, end_date = _parse_date_range(request)

    title = ""
    headers = []
    rows = []
    total_row = None

    if report_type == 'payments':
        title = f"To'lovlar hisoboti ({start_date} dan {end_date} gacha)"
        headers = ["ID", "O'quvchi", "Summa (so'm)", "To'lov usuli", "Sana", "Kvitansiya"]
        payments = Payment.objects.filter(
            status=Payment.Status.COMPLETED,
            paid_at__date__gte=start_date,
            paid_at__date__lte=end_date
        ).select_related('student')
        total_sum = Decimal('0.00')
        for p in payments:
            rows.append([p.id, p.student.full_name, p.amount, p.get_method_display(), p.paid_at.strftime('%Y-%m-%d %H:%M'), p.reference])
            total_sum += p.amount
        total_row = ["JAMI", "", total_sum, "", "", ""]

    elif report_type == 'debtors':
        title = f"Qarzdor o'quvchilar ro'yxati ({timezone.now().strftime('%Y-%m-%d')})"
        headers = ["O'quvchi", "Telefon", "Ota-onasi telefoni", "Guruhlar", "Qarzdorlik (so'm)"]
        debtors = get_debtors_report()
        total_debt = Decimal('0.00')
        for d in debtors:
            rows.append([d['student'].full_name, d['student'].phone, d['student'].parent_phone, d['active_groups'], d['total_debt']])
            total_debt += d['total_debt']
        total_row = ["JAMI", "", "", "", total_debt]

    elif report_type == 'cash_flow':
        if not request.user.is_owner:
            return HttpResponse("Ruxsat yo'q", status=403)
        title = f"Pul oqimi hisoboti ({start_date} dan {end_date} gacha)"
        headers = ["Modda", "Tafsilot", "Summa (so'm)"]
        cf = get_cash_flow_report(start_date, end_date)
        rows.append(["KIRIM (Tushumlar)", "O'quvchilar to'lovlari", cf['inflows_total']])
        rows.append(["CHIQIM (Ish haqi)", "O'qituvchilarga to'langan oylik", cf['salaries_total']])
        rows.append(["CHIQIM (Xarajatlar)", "Operatsion xarajatlar", cf['expenses_total']])
        total_row = ["SOF PUL OQIMI", "Kirim - Chiqim", cf['net_cash_flow']]

    elif report_type == 'expenses':
        if not request.user.is_owner:
            return HttpResponse("Ruxsat yo'q", status=403)
        title = f"Xarajatlar hisoboti ({start_date} dan {end_date} gacha)"
        headers = ["ID", "Toifa", "Tavsif", "Summa (so'm)", "To'lov usuli", "Sana"]
        expenses = Expense.objects.filter(
            status=Expense.Status.ACTIVE,
            occurred_at__gte=start_date,
            occurred_at__lte=end_date
        )
        total_exp = Decimal('0.00')
        for e in expenses:
            rows.append([e.id, e.get_category_display(), e.description, e.amount, e.get_method_display(), e.occurred_at.strftime('%Y-%m-%d')])
            total_exp += e.amount
        total_row = ["JAMI", "", "", total_exp, "", ""]

    if export_format == 'pdf':
        pdf_buffer = export_report_to_pdf(title=title, headers=headers, rows=rows, summary_text=f"Hisobot sanasi: {timezone.now().strftime('%Y-%m-%d %H:%M')}")
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report_type}_{timezone.now().strftime("%Y%m%d")}.pdf"'
        return response
    else:
        excel_buffer = export_report_to_excel(title=title, headers=headers, rows=rows, total_row=total_row)
        response = HttpResponse(
            excel_buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{report_type}_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        return response


@admin_or_owner_required
def reports_hub_view(request):
    start_date, end_date = _parse_date_range(request)
    is_owner = request.user.is_owner

    # High level statistics for quick cards
    payments_total = Payment.objects.filter(
        status=Payment.Status.COMPLETED,
        paid_at__date__gte=start_date,
        paid_at__date__lte=end_date
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    charges_total = MonthlyCharge.objects.exclude(
        status=MonthlyCharge.Status.CANCELLED
    ).filter(
        billing_month__gte=start_date,
        billing_month__lte=end_date
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    debtors = get_debtors_report()
    debtors_count = len(debtors)
    total_debt = sum(d['total_debt'] for d in debtors) if debtors else Decimal('0.00')

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'is_owner': is_owner,
        'payments_total': payments_total,
        'charges_total': charges_total,
        'debtors_count': debtors_count,
        'total_debt': total_debt,
    }

    if is_owner:
        expenses_total = Expense.objects.filter(
            status=Expense.Status.ACTIVE,
            occurred_at__gte=start_date,
            occurred_at__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        salaries_total = SalaryPayment.objects.filter(
            status=SalaryPayment.Status.COMPLETED,
            paid_at__date__gte=start_date,
            paid_at__date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        net_cash = payments_total - (expenses_total + salaries_total)

        context.update({
            'expenses_total': expenses_total,
            'salaries_total': salaries_total,
            'net_cash': net_cash,
        })

    return render(request, 'reporting/reports_hub.html', context)

