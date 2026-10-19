from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('expenses/', views.expenses_list_view, name='expenses_list'),
    path('expenses/create/', views.expense_create_view, name='expense_create'),
    path('expenses/<int:expense_id>/cancel/', views.expense_cancel_view, name='expense_cancel'),
]
