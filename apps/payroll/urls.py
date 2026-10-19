from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    path('', views.salaries_list_view, name='salaries_list'),
    path('generate/', views.salary_generate_view, name='salary_generate'),
    path('bulk-generate/', views.salary_bulk_generate_view, name='bulk_generate'),
    path('<int:salary_id>/approve/', views.salary_approve_view, name='salary_approve'),
    path('<int:salary_id>/pay/', views.salary_payment_create_view, name='salary_pay'),
    path('<int:salary_id>/cancel/', views.salary_cancel_view, name='salary_cancel'),
    path('payments/<int:payment_id>/cancel/', views.salary_payment_cancel_view, name='salary_payment_cancel'),
]
