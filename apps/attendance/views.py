from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from apps.accounts.decorators import admin_or_owner_required
from apps.audit.services import log_audit
from .models import Lesson, AttendanceRecord
from .forms import LessonForm
from apps.academics.models import StudyGroup, Enrollment


@admin_or_owner_required
def lessons_list_view(request):
    group_id = request.GET.get('group')
    date_filter = request.GET.get('date')

    lessons = Lesson.objects.select_related('group', 'group__course', 'group__teacher').prefetch_related('attendances')

    if group_id:
        lessons = lessons.filter(group_id=group_id)
    if date_filter:
        lessons = lessons.filter(date=date_filter)

    groups = StudyGroup.objects.filter(is_active=True).order_by('name')

    return render(request, 'attendance/lessons_list.html', {
        'lessons': lessons.order_by('-date', '-starts_at')[:50],
        'groups': groups,
        'selected_group': group_id,
        'selected_date': date_filter,
    })


@admin_or_owner_required
def lesson_create_view(request, group_id=None):
    initial = {'date': timezone.now().date()}
    if group_id:
        group = get_object_or_404(StudyGroup, id=group_id)
        initial['group'] = group

    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save()
            log_audit(
                actor=request.user,
                action='CREATE',
                entity_type='Lesson',
                entity_id=lesson.id,
                changes_after={'group': lesson.group.name, 'date': lesson.date.isoformat()},
                reason="Yangi dars jadvali yaratildi"
            )
            messages.success(request, f"Dars muvaffaqiyatli rejalashtirildi: {lesson.group.name} ({lesson.date}).")
            return redirect('attendance:lesson_attendance', lesson_id=lesson.id)
    else:
        form = LessonForm(initial=initial)

    return render(request, 'attendance/lesson_form.html', {'form': form, 'title': "Yangi dars belgilash"})


@admin_or_owner_required
def lesson_attendance_view(request, lesson_id):
    """
    Attendance journal for a specific lesson.
    Checks that students were enrolled in the group on the lesson's date.
    When a mark is updated, records AuditLog of the change.
    """
    lesson = get_object_or_404(
        Lesson.objects.select_related('group', 'group__course', 'group__teacher'),
        id=lesson_id
    )

    # Get active enrollments on the lesson's date
    active_enrollments = lesson.group.enrollments.filter(
        start_date__lte=lesson.date
    ).filter(
        models_q_end_date(lesson.date)
    ).select_related('student')

    enrolled_students = [e.student for e in active_enrollments]

    # Existing attendance records map
    existing_attendances = {
        att.student_id: att for att in lesson.attendances.all()
    }

    if request.method == 'POST':
        with transaction.atomic():
            for student in enrolled_students:
                status_key = f"status_{student.id}"
                note_key = f"note_{student.id}"

                new_status = request.POST.get(status_key)
                new_note = request.POST.get(note_key, "").strip()

                if new_status:
                    if student.id in existing_attendances:
                        att_record = existing_attendances[student.id]
                        old_status = att_record.status
                        old_note = att_record.notes

                        if old_status != new_status or old_note != new_note:
                            att_record.status = new_status
                            att_record.notes = new_note
                            att_record.marked_by = request.user
                            att_record.save(update_fields=['status', 'notes', 'marked_by', 'updated_at'])

                            log_audit(
                                actor=request.user,
                                action='UPDATE',
                                entity_type='AttendanceRecord',
                                entity_id=att_record.id,
                                changes_before={'status': old_status, 'note': old_note},
                                changes_after={'status': new_status, 'note': new_note},
                                reason=f"{student.full_name} davomati o'zgartirildi"
                            )
                    else:
                        att_record = AttendanceRecord.objects.create(
                            lesson=lesson,
                            student=student,
                            status=new_status,
                            notes=new_note,
                            marked_by=request.user
                        )
                        log_audit(
                            actor=request.user,
                            action='CREATE',
                            entity_type='AttendanceRecord',
                            entity_id=att_record.id,
                            changes_after={'student': student.full_name, 'status': new_status},
                            reason="Davomat belgilandi"
                        )

            lesson.status = Lesson.Status.COMPLETED
            lesson.save(update_fields=['status'])

        messages.success(request, f"{lesson.group.name} uchun davomat muvaffaqiyatli saqlandi.")
        return redirect('attendance:lesson_attendance', lesson_id=lesson.id)

    # Build student attendance rows for template
    attendance_rows = []
    for student in enrolled_students:
        att = existing_attendances.get(student.id)
        attendance_rows.append({
            'student': student,
            'status': att.status if att else 'present',
            'notes': att.notes if att else '',
            'marked_at': att.marked_at if att else None,
            'marked_by': att.marked_by if att else None,
        })

    return render(request, 'attendance/lesson_attendance.html', {
        'lesson': lesson,
        'attendance_rows': attendance_rows,
        'status_choices': AttendanceRecord.Status.choices,
    })


def models_q_end_date(target_date):
    from django.db.models import Q
    return Q(end_date__isnull=True) | Q(end_date__gte=target_date)
