from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
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

    lessons = Lesson.objects.select_related('group', 'group__course', 'group__teacher').annotate(
        present_count=Count('attendances', filter=Q(attendances__status__in=['present', 'late'])),
        absent_count=Count('attendances', filter=Q(attendances__status__in=['absent', 'excused'])),
    )

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
    When marked as absent, absence_reason and comment/note are strictly mandatory.
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
        errors = []
        parsed_data = {}

        # First pass: validate all inputs
        for student in enrolled_students:
            status_key = f"status_{student.id}"
            reason_key = f"reason_{student.id}"
            note_key = f"note_{student.id}"

            new_status = request.POST.get(status_key)
            new_reason = request.POST.get(reason_key, "").strip()
            new_note = request.POST.get(note_key, "").strip()

            if new_status:
                if new_status == AttendanceRecord.Status.ABSENT:
                    if not new_reason or new_reason not in AttendanceRecord.AbsenceReason.values:
                        errors.append(f"{student.full_name}: Qatnashmadi deb belgilanganda sabab tanlanishi shart.")

                parsed_data[student.id] = {
                    'status': new_status,
                    'reason': new_reason if new_status == AttendanceRecord.Status.ABSENT else '',
                    'note': new_note,
                }

        if errors:
            for err in errors:
                messages.error(request, err)
            # Render with user entered values
            attendance_rows = []
            for student in enrolled_students:
                item = parsed_data.get(student.id)
                att = existing_attendances.get(student.id)
                attendance_rows.append({
                    'student': student,
                    'status': item['status'] if item else (att.status if att else 'present'),
                    'absence_reason': item['reason'] if item else (att.absence_reason if att else ''),
                    'notes': item['note'] if item else (att.notes if att else ''),
                    'marked_at': att.marked_at if att else None,
                    'marked_by': att.marked_by if att else None,
                })
            return render(request, 'attendance/lesson_attendance.html', {
                'lesson': lesson,
                'attendance_rows': attendance_rows,
                'status_choices': AttendanceRecord.Status.choices,
                'absence_reasons': AttendanceRecord.AbsenceReason.choices,
            })

        with transaction.atomic():
            for student in enrolled_students:
                if student.id not in parsed_data:
                    continue

                item = parsed_data[student.id]
                new_status = item['status']
                new_reason = item['reason']
                new_note = item['note']

                if student.id in existing_attendances:
                    att_record = existing_attendances[student.id]
                    old_status = att_record.status
                    old_note = att_record.notes
                    old_reason = att_record.absence_reason

                    if old_status != new_status or old_note != new_note or old_reason != new_reason:
                        att_record.status = new_status
                        att_record.absence_reason = new_reason
                        att_record.notes = new_note
                        att_record.marked_by = request.user
                        att_record.save(update_fields=['status', 'absence_reason', 'notes', 'marked_by', 'updated_at'])

                        log_audit(
                            actor=request.user,
                            action='UPDATE',
                            entity_type='AttendanceRecord',
                            entity_id=att_record.id,
                            changes_before={'status': old_status, 'absence_reason': old_reason, 'note': old_note},
                            changes_after={'status': new_status, 'absence_reason': new_reason, 'note': new_note},
                            reason=f"{student.full_name} davomati o'zgartirildi"
                        )
                else:
                    att_record = AttendanceRecord.objects.create(
                        lesson=lesson,
                        student=student,
                        status=new_status,
                        absence_reason=new_reason,
                        notes=new_note,
                        marked_by=request.user
                    )
                    log_audit(
                        actor=request.user,
                        action='CREATE',
                        entity_type='AttendanceRecord',
                        entity_id=att_record.id,
                        changes_after={
                            'student': student.full_name,
                            'status': new_status,
                            'absence_reason': new_reason,
                            'note': new_note
                        },
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
            'absence_reason': att.absence_reason if att else '',
            'notes': att.notes if att else '',
            'marked_at': att.marked_at if att else None,
            'marked_by': att.marked_by if att else None,
        })

    return render(request, 'attendance/lesson_attendance.html', {
        'lesson': lesson,
        'attendance_rows': attendance_rows,
        'status_choices': AttendanceRecord.Status.choices,
        'absence_reasons': AttendanceRecord.AbsenceReason.choices,
    })


@admin_or_owner_required
def student_absence_history_view(request, student_id):
    """
    Detailed absence history view for a student.
    Shows reason, comment, date, marked_by admin, and group info.
    """
    from apps.students.models import Student
    student = get_object_or_404(Student, id=student_id)

    absences = AttendanceRecord.objects.filter(
        student=student,
        status=AttendanceRecord.Status.ABSENT
    ).select_related('lesson', 'lesson__group', 'lesson__group__course', 'marked_by').order_by('-lesson__date', '-marked_at')

    # Optional filter by reason
    reason_filter = request.GET.get('reason', '').strip()
    if reason_filter:
        absences = absences.filter(absence_reason=reason_filter)

    # Optional date filters
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    if date_from:
        absences = absences.filter(lesson__date__gte=date_from)
    if date_to:
        absences = absences.filter(lesson__date__lte=date_to)

    total_absences = AttendanceRecord.objects.filter(
        student=student,
        status=AttendanceRecord.Status.ABSENT
    ).count()

    return render(request, 'attendance/student_absence_history.html', {
        'student': student,
        'absences': absences,
        'total_absences': total_absences,
        'selected_reason': reason_filter,
        'date_from': date_from,
        'date_to': date_to,
        'reason_choices': AttendanceRecord.AbsenceReason.choices,
    })


def models_q_end_date(target_date):
    from django.db.models import Q
    return Q(end_date__isnull=True) | Q(end_date__gte=target_date)
