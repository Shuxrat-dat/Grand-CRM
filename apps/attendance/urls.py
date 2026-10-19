from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('lessons/', views.lessons_list_view, name='lessons_list'),
    path('lessons/create/', views.lesson_create_view, name='lesson_create'),
    path('groups/<int:group_id>/lessons/create/', views.lesson_create_view, name='group_lesson_create'),
    path('lessons/<int:lesson_id>/attendance/', views.lesson_attendance_view, name='lesson_attendance'),
]
