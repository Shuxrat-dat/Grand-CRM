from django.contrib import admin
from django.urls import path, include
from apps.reporting.views import dashboard_view
from apps.accounts.search_views import (
    search_students_api,
    search_teachers_api,
    search_enrollments_api,
    search_universal_api
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_view, name='dashboard'),
    path('auth/', include('apps.accounts.urls')),
    path('leads/', include('apps.leads.urls')),
    path('students/', include('apps.students.urls')),
    path('academics/', include('apps.academics.urls')),
    path('attendance/', include('apps.attendance.urls')),
    path('billing/', include('apps.billing.urls')),
    path('payroll/', include('apps.payroll.urls')),
    path('finance/', include('apps.finance.urls')),
    path('reports/', include('apps.reporting.urls')),
    path('audit/', include('apps.audit.urls')),

    # Dynamic Search APIs
    path('api/search/students/', search_students_api, name='api_search_students'),
    path('api/search/teachers/', search_teachers_api, name='api_search_teachers'),
    path('api/search/enrollments/', search_enrollments_api, name='api_search_enrollments'),
    path('api/search/universal/', search_universal_api, name='api_search_universal'),
]
