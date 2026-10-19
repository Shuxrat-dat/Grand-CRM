from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError

from apps.accounts.decorators import owner_required
from .models import Expense
from .forms import ExpenseForm
from apps.billing.forms import CancelReasonForm
from .services import create_expense, cancel_expense


@owner_required
def expenses_list_view(request):
    category_filter = request.GET.get('category', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    status_filter = request.GET.get('status', 'active')

    expenses = Expense.objects.select_related('created_by').order_by('-occurred_at', '-created_at')

    if category_filter:
        expenses = expenses.filter(category=category_filter)
    if start_date:
        expenses = expenses.filter(occurred_at__gte=start_date)
    if end_date:
        expenses = expenses.filter(occurred_at__lte=end_date)
    if status_filter and status_filter != 'all':
        expenses = expenses.filter(status=status_filter)

    return render(request, 'finance/expenses_list.html', {
        'expenses': expenses[:100],
        'category_filter': category_filter,
        'start_date': start_date,
        'end_date': end_date,
        'status_filter': status_filter,
        'category_choices': Expense.Category.choices,
    })


@owner_required
def expense_create_view(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            try:
                expense = create_expense(
                    category=form.cleaned_data['category'],
                    amount=form.cleaned_data['amount'],
                    occurred_at=form.cleaned_data['occurred_at'],
                    description=form.cleaned_data['description'],
                    method=form.cleaned_data['method'],
                    user=request.user
                )
                messages.success(request, f"{expense.amount} so'm xarajat muvaffaqiyatli qayd etildi.")
                return redirect('finance:expenses_list')
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = ExpenseForm()

    return render(request, 'finance/expense_form.html', {'form': form, 'title': "Yangi xarajat kiritish"})


@owner_required
def expense_cancel_view(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)

    if request.method == 'POST':
        form = CancelReasonForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            try:
                cancel_expense(expense_id=expense.id, user=request.user, reason=reason)
                messages.warning(request, f"Xarajat #{expense.id} bekor qilindi.")
                return redirect('finance:expenses_list')
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = CancelReasonForm()

    return render(request, 'finance/confirm_cancel.html', {
        'form': form,
        'title': f"Xarajatni bekor qilish: #{expense.id} - {expense.get_category_display()}",
        'expense': expense
    })
