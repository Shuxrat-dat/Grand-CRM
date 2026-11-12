from django.contrib import admin
from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'course', 'source', 'status', 'assigned_to', 'created_at', 'converted_student')
    list_filter = ('status', 'source', 'course', 'created_at')
    search_fields = ('full_name', 'phone', 'notes')
    ordering = ('-created_at',)
