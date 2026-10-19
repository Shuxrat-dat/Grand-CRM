from django.urls import path
from . import views

app_name = 'reporting'

urlpatterns = [
    path('', views.reports_hub_view, name='reports_hub'),
    path('cash-flow/', views.report_cash_flow_view, name='cash_flow'),
    path('accrual-profit/', views.report_accrual_profit_view, name='accrual_profit'),
    path('payments/', views.report_payments_view, name='payments'),
    path('charges/', views.report_charges_view, name='charges'),
    path('debtors/', views.report_debtors_view, name='debtors'),
    path('group-revenue/', views.report_group_revenue_view, name='group_revenue'),
    path('attendance/', views.report_attendance_view, name='attendance'),
    path('payroll/', views.report_payroll_view, name='payroll'),
    path('expenses/', views.report_expenses_view, name='expenses'),
    path('export/<str:report_type>/', views.export_report_view, name='export_report'),
]
