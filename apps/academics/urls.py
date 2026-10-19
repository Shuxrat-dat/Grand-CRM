from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    # Courses
    path('courses/', views.courses_list_view, name='courses_list'),
    path('courses/create/', views.course_create_view, name='course_create'),
    path('courses/<int:course_id>/edit/', views.course_edit_view, name='course_edit'),

    # Teachers
    path('teachers/', views.teachers_list_view, name='teachers_list'),
    path('teachers/create/', views.teacher_create_view, name='teacher_create'),
    path('teachers/<int:teacher_id>/', views.teacher_detail_view, name='teacher_detail'),
    path('teachers/<int:teacher_id>/edit/', views.teacher_edit_view, name='teacher_edit'),
    path('teachers/<int:teacher_id>/rates/create/', views.teacher_salary_rate_create_view, name='teacher_salary_rate_create'),

    # Groups & Schedules
    path('groups/', views.groups_list_view, name='groups_list'),
    path('groups/create/', views.group_create_view, name='group_create'),
    path('groups/<int:group_id>/', views.group_detail_view, name='group_detail'),
    path('groups/<int:group_id>/edit/', views.group_edit_view, name='group_edit'),
    path('groups/<int:group_id>/schedules/add/', views.group_schedule_add_view, name='group_schedule_add'),

    # Enrollments
    path('enroll/', views.enroll_student_view, name='enroll_student'),
    path('groups/<int:group_id>/enroll/', views.enroll_student_view, name='group_enroll_student'),
    path('enrollments/<int:enrollment_id>/transfer/', views.transfer_student_view, name='transfer_student'),
    path('enrollments/<int:enrollment_id>/drop/', views.drop_student_view, name='drop_student'),
]
