from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('users/', views.admin_users_list_view, name='admin_users_list'),
    path('users/create/', views.admin_user_create_view, name='admin_user_create'),
    path('users/<int:user_id>/edit/', views.admin_user_edit_view, name='admin_user_edit'),
    path('users/<int:user_id>/toggle/', views.admin_user_toggle_view, name='admin_user_toggle'),
    path('settings/', views.center_settings_view, name='settings'),
]
