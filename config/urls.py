from django.contrib import admin
from django.urls import path, include
from apps.reporting.views import dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_view, name='dashboard'),
    path('auth/', include('apps.accounts.urls')),
    path('students/', include('apps.students.urls')),
    path('academics/', include('apps.academics.urls')),
    path('attendance/', include('apps.attendance.urls')),
    path('billing/', include('apps.billing.urls')),
    path('payroll/', include('apps.payroll.urls')),
    path('finance/', include('apps.finance.urls')),
    path('reports/', include('apps.reporting.urls')),
    path('audit/', include('apps.audit.urls')),
]
