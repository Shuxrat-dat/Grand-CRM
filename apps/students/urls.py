from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.students_list_view, name='students_list'),
    path('create/', views.student_create_view, name='student_create'),
    path('<int:student_id>/', views.student_detail_view, name='student_detail'),
    path('<int:student_id>/edit/', views.student_edit_view, name='student_edit'),
    path('<int:student_id>/archive/', views.student_archive_view, name='student_archive'),
    path('<int:student_id>/restore/', views.student_restore_view, name='student_restore'),
]
