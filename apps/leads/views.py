from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from apps.accounts.decorators import admin_or_owner_required
from apps.audit.services import log_audit
from .models import Lead
from .forms import LeadForm, LeadConvertForm
from apps.academics.models import StudyGroup, Course, Enrollment
from apps.students.models import Student
from apps.accounts.models import User


@admin_or_owner_required
def leads_list_view(request):
    """
    Main leads dashboard and listing view.
    Includes searching, multi-filter, sorting, pagination,
    and lead-to-student conversion statistics.
    """
    qs = Lead.objects.select_related('course', 'assigned_to', 'converted_student', 'converted_by').all()

    # Base statistics across ALL leads in database
    total_leads_count = Lead.objects.count()
    converted_leads_count = Lead.objects.filter(status=Lead.Status.CONVERTED).count()
    new_leads_count = Lead.objects.filter(status=Lead.Status.YANGI).count()
    active_leads_count = Lead.objects.filter(
        status__in=[
            Lead.Status.BOGLANILDI,
            Lead.Status.SINOV_DARSI,
            Lead.Status.KUTILMOQDA,
            Lead.Status.QAYTA_ALOQA,
        ]
    ).count()

    conversion_rate = 0.0
    if total_leads_count > 0:
        conversion_rate = round((converted_leads_count / total_leads_count) * 100, 1)

    # Search query
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(full_name__icontains=q) |
            Q(phone__icontains=q) |
            Q(notes__icontains=q)
        )

    # Filters
    status_filter = request.GET.get('status', '').strip()
    if status_filter and status_filter != 'all':
        qs = qs.filter(status=status_filter)

    course_filter = request.GET.get('course', '').strip()
    if course_filter:
        qs = qs.filter(course_id=course_filter)

    source_filter = request.GET.get('source', '').strip()
    if source_filter:
        qs = qs.filter(source=source_filter)

    assigned_filter = request.GET.get('assigned_to', '').strip()
    if assigned_filter:
        qs = qs.filter(assigned_to_id=assigned_filter)

    date_from = request.GET.get('date_from', '').strip()
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)

    date_to = request.GET.get('date_to', '').strip()
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    allowed_sorts = ['-created_at', 'created_at', 'full_name', '-full_name', 'status', '-status']
    if sort_by in allowed_sorts:
        qs = qs.order_by(sort_by)
    else:
        qs = qs.order_by('-created_at')

    # Pagination
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Active groups for conversion modals
    active_groups = StudyGroup.objects.filter(is_active=True).select_related('course', 'teacher').order_by('name')
    courses = Course.objects.filter(is_active=True).order_by('name')
    staff_users = User.objects.filter(is_active=True).order_by('first_name', 'username')

    return render(request, 'leads/leads_list.html', {
        'page_obj': page_obj,
        'leads': page_obj.object_list,
        'q': q,
        'status_filter': status_filter,
        'course_filter': course_filter,
        'source_filter': source_filter,
        'assigned_filter': assigned_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort_by': sort_by,
        # Stats
        'total_leads_count': total_leads_count,
        'converted_leads_count': converted_leads_count,
        'new_leads_count': new_leads_count,
        'active_leads_count': active_leads_count,
        'conversion_rate': conversion_rate,
        # Choices & dropdowns
        'status_choices': Lead.Status.choices,
        'source_choices': Lead.Source.choices,
        'courses': courses,
        'staff_users': staff_users,
        'active_groups': active_groups,
    })


@admin_or_owner_required
def lead_create_view(request):
    """
    Creates a new lead.
    """
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            lead = form.save()
            log_audit(
                actor=request.user,
                action='CREATE',
                entity_type='Lead',
                entity_id=lead.id,
                changes_after={
                    'full_name': lead.full_name,
                    'phone': lead.phone,
                    'source': lead.source,
                    'status': lead.status,
                },
                reason="Yangi lid tizimga kiritildi"
            )
            messages.success(request, f"Lid '{lead.full_name}' muvaffaqiyatli saqlandi.")
            return redirect('leads:leads_list')
    else:
        form = LeadForm()

    return render(request, 'leads/lead_form.html', {
        'form': form,
        'title': "Yangi lid qo‘shish",
    })


@admin_or_owner_required
def lead_edit_view(request, lead_id):
    """
    Edit existing lead information, status, notes, or assigned staff.
    """
    lead = get_object_or_404(Lead, id=lead_id)
    old_data = {
        'full_name': lead.full_name,
        'phone': lead.phone,
        'status': lead.status,
        'source': lead.source,
        'assigned_to': lead.assigned_to.username if lead.assigned_to else None,
    }

    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            updated_lead = form.save()
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='Lead',
                entity_id=lead.id,
                changes_before=old_data,
                changes_after={
                    'full_name': updated_lead.full_name,
                    'phone': updated_lead.phone,
                    'status': updated_lead.status,
                    'source': updated_lead.source,
                    'assigned_to': updated_lead.assigned_to.username if updated_lead.assigned_to else None,
                },
                reason="Lid ma'lumotlari yangilandi"
            )
            messages.success(request, f"Lid '{updated_lead.full_name}' ma’lumotlari yangilandi.")
            return redirect('leads:leads_list')
    else:
        form = LeadForm(instance=lead)

    return render(request, 'leads/lead_form.html', {
        'form': form,
        'title': f"Lidni tahrirlash: {lead.full_name}",
        'lead': lead,
    })


@admin_or_owner_required
def lead_convert_view(request, lead_id):
    """
    Core Feature: Converts a lead into a Student and enrolls them into a StudyGroup.
    Prevents duplicate conversion if already converted.
    """
    lead = get_object_or_404(
        Lead.objects.select_related('course', 'converted_student'),
        id=lead_id
    )

    # 1. Prevent duplicate conversion
    if lead.is_converted:
        messages.warning(
            request,
            f"Ushbu lid allaqachon '{lead.converted_student.full_name}' o‘quvchisiga aylantirilgan! Takroriy yaratish taqiqlanadi."
        )
        return redirect('students:student_detail', student_id=lead.converted_student.id)

    if request.method == 'POST':
        form = LeadConvertForm(request.POST, course=lead.course)
        if form.is_valid():
            group = form.cleaned_data['group']
            start_date = form.cleaned_data['start_date']
            monthly_price = form.cleaned_data.get('monthly_price')
            parent_phone = form.cleaned_data.get('parent_phone', '').strip()

            if not monthly_price:
                monthly_price = group.course.default_monthly_price

            with transaction.atomic():
                # Re-check inside transaction lock
                lead_locked = Lead.objects.select_for_update().get(id=lead.id)
                if lead_locked.is_converted:
                    messages.warning(request, "Ushbu lid boshqa xodim tomonidan allaqachon aylantirilgan!")
                    return redirect('leads:leads_list')

                # Create Student in students app
                student_notes = f"Liddan aylantirildi. Manba: {lead_locked.get_source_display()}."
                if lead_locked.notes:
                    student_notes += f" Qo‘shimcha qayd: {lead_locked.notes}"

                student = Student.objects.create(
                    full_name=lead_locked.full_name,
                    phone=lead_locked.phone,
                    parent_phone=parent_phone,
                    joined_at=start_date,
                    notes=student_notes,
                    status=Student.Status.ACTIVE
                )

                # Create Enrollment in selected group
                enrollment = Enrollment.objects.create(
                    student=student,
                    group=group,
                    start_date=start_date,
                    monthly_price=monthly_price,
                    status=Enrollment.Status.ACTIVE
                )

                # Update lead record
                lead_locked.converted_student = student
                lead_locked.status = Lead.Status.CONVERTED
                lead_locked.converted_at = timezone.now()
                lead_locked.converted_by = request.user
                lead_locked.save(update_fields=['converted_student', 'status', 'converted_at', 'converted_by', 'updated_at'])

                log_audit(
                    actor=request.user,
                    action='CONVERT_LEAD',
                    entity_type='Lead',
                    entity_id=lead_locked.id,
                    changes_after={
                        'student_id': student.id,
                        'student_name': student.full_name,
                        'group': group.name,
                        'course': group.course.name,
                        'monthly_price': str(monthly_price),
                    },
                    reason=f"Lid '{lead_locked.full_name}' muvaffaqiyatli o‘quvchiga aylantirildi"
                )

            messages.success(
                request,
                f"Ajoyib! '{lead.full_name}' muvaffaqiyatli o‘quvchiga aylantirildi va '{group.name}' guruhiga qo‘shildi."
            )
            return redirect('students:student_detail', student_id=student.id)
    else:
        # Prepopulate form
        initial_price = lead.course.default_monthly_price if lead.course else None
        form = LeadConvertForm(initial={
            'start_date': timezone.now().date(),
            'monthly_price': initial_price,
        }, course=lead.course)

    return render(request, 'leads/lead_convert.html', {
        'lead': lead,
        'form': form,
    })


@admin_or_owner_required
def lead_delete_view(request, lead_id):
    """
    Deletes a lead with confirmation.
    """
    lead = get_object_or_404(Lead, id=lead_id)

    if request.method == 'POST':
        lead_name = lead.full_name
        lead_id_str = str(lead.id)
        lead.delete()

        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='Lead',
            entity_id=lead_id_str,
            reason=f"Lid '{lead_name}' o‘chirildi"
        )
        messages.warning(request, f"Lid '{lead_name}' tizimdan o‘chirildi.")
        return redirect('leads:leads_list')

    return render(request, 'leads/lead_confirm_delete.html', {'lead': lead})
