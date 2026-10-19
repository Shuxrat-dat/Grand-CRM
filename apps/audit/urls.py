from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('', views.audit_logs_list_view, name='audit_logs_list'),
]
