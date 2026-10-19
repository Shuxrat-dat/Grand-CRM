from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # Charges
    path('charges/', views.charges_list_view, name='charges_list'),
    path('charges/create/', views.charge_create_view, name='charge_create'),
    path('charges/bulk/', views.generate_bulk_charges_view, name='bulk_charges'),
    path('charges/<int:charge_id>/cancel/', views.charge_cancel_view, name='charge_cancel'),

    # Payments
    path('payments/', views.payments_list_view, name='payments_list'),
    path('payments/create/', views.payment_create_view, name='payment_create'),
    path('students/<int:student_id>/payments/create/', views.payment_create_view, name='student_payment_create'),
    path('payments/<int:payment_id>/', views.payment_detail_view, name='payment_detail'),
    path('payments/<int:payment_id>/cancel/', views.payment_cancel_view, name='payment_cancel'),

    # Debtors
    path('debtors/', views.debtors_list_view, name='debtors_list'),
]
