from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    path('', views.leads_list_view, name='leads_list'),
    path('create/', views.lead_create_view, name='lead_create'),
    path('<int:lead_id>/edit/', views.lead_edit_view, name='lead_edit'),
    path('<int:lead_id>/convert/', views.lead_convert_view, name='lead_convert'),
    path('<int:lead_id>/delete/', views.lead_delete_view, name='lead_delete'),
]
