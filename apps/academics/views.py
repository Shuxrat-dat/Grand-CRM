import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from apps.accounts.decorators import admin_or_owner_required, owner_required
from apps.audit.services import log_audit
from .models import Course, Teacher, TeacherSalaryRate, StudyGroup, GroupSchedule, Enrollment, EnrollmentPriceHistory
from .forms import (
    CourseForm, TeacherForm, TeacherSalaryRateForm,
    StudyGroupForm, GroupScheduleForm, EnrollmentForm, TransferEnrollmentForm,
    GroupScheduleMultiSlotForm, LessonGenerateForm, EnrollmentPriceUpdateForm
)
from .services import (
    check_schedule_conflicts, create_schedule_slots,
    generate_lessons_from_schedules, update_enrollment_price,
    revert_enrollment_to_standard_price
)
from apps.students.models import Student
from apps.attendance.models import Lesson


# --- COURSES ---

@admin_or_owner_required
def courses_list_view(request):
    courses = Course.objects.all().order_by('name')
    return render(request, 'academics/courses_list.html', {'courses': courses})


@owner_required
def course_create_view(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save()
            log_audit(
                actor=request.user,
                action='CREATE',
                entity_type='Course',
                entity_id=course.id,
                changes_after={'name': course.name, 'price': str(course.default_monthly_price)},
                reason="Yangi kurs qo'shildi"
            )
            messages.success(request, f"Kurs '{course.name}' muvaffaqiyatli yaratildi.")
            return redirect('academics:courses_list')
    else:
        form = CourseForm()

    return render(request, 'academics/course_form.html', {'form': form, 'title': "Yangi kurs yaratish"})


@owner_required
def course_edit_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    old_price = course.default_monthly_price

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            updated_course = form.save()
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='Course',
                entity_id=course.id,
                changes_before={'price': str(old_price)},
                changes_after={'price': str(updated_course.default_monthly_price)},
                reason="Kurs narxi yoki parametrlari o'zgartirildi (mavjud guruhlar narxi saqlanadi)"
            )
            messages.success(request, f"'{course.name}' kursi yangilandi.")
            return redirect('academics:courses_list')
    else:
        form = CourseForm(instance=course)

    return render(request, 'academics/course_form.html', {
        'form': form,
        'title': f"Kursni tahrirlash: {course.name}",
        'course': course
    })


# --- TEACHERS ---

@admin_or_owner_required
def teachers_list_view(request):
    teachers = Teacher.objects.all().prefetch_related('groups').order_by('full_name')
    return render(request, 'academics/teachers_list.html', {'teachers': teachers})


@owner_required
def teacher_create_view(request):
    if request.method == 'POST':
        form = TeacherForm(request.POST)
        rate_form = TeacherSalaryRateForm(request.POST)
        if form.is_valid() and rate_form.is_valid():
            with transaction.atomic():
                teacher = form.save()
                rate = rate_form.save(commit=False)
                rate.teacher = teacher
                rate.save()

                log_audit(
                    actor=request.user,
                    action='CREATE',
                    entity_type='Teacher',
                    entity_id=teacher.id,
                    changes_after={'name': teacher.full_name, 'rate': str(rate.monthly_amount)},
                    reason="Yangi o'qituvchi va boshlang'ich stavka kiritildi"
                )
            messages.success(request, f"O'qituvchi '{teacher.full_name}' muvaffaqiyatli saqlandi.")
            return redirect('academics:teacher_detail', teacher_id=teacher.id)
    else:
        form = TeacherForm()
        rate_form = TeacherSalaryRateForm()

    return render(request, 'academics/teacher_form.html', {
        'form': form,
        'rate_form': rate_form,
        'title': "Yangi o'qituvchi qo'shish"
    })


@admin_or_owner_required
def teacher_detail_view(request, teacher_id):
    teacher = get_object_or_404(
        Teacher.objects.prefetch_related('groups__course', 'salary_rates', 'salary_records'),
        id=teacher_id
    )
    current_rate = teacher.get_salary_rate_for_date()
    salary_rates = teacher.salary_rates.all().order_by('-valid_from')
    salary_records = teacher.salary_records.all().order_by('-period_month') if request.user.is_owner else []

    return render(request, 'academics/teacher_detail.html', {
        'teacher': teacher,
        'current_rate': current_rate,
        'salary_rates': salary_rates,
        'salary_records': salary_records,
        'rate_form': TeacherSalaryRateForm() if request.user.is_owner else None,
    })


@owner_required
def teacher_edit_view(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    if request.method == 'POST':
        form = TeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            form.save()
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='Teacher',
                entity_id=teacher.id,
                reason="O'qituvchi ma'lumotlari tahrirlandi"
            )
            messages.success(request, f"'{teacher.full_name}' ma'lumotlari yangilandi.")
            return redirect('academics:teacher_detail', teacher_id=teacher.id)
    else:
        form = TeacherForm(instance=teacher)

    return render(request, 'academics/teacher_form.html', {
        'form': form,
        'title': f"O'qituvchini tahrirlash: {teacher.full_name}",
        'teacher': teacher
    })


@owner_required
def teacher_salary_rate_create_view(request, teacher_id):
    """
    Owner updates fixed salary rate from a specified date.
    Old rates and past salary records remain intact.
    """
    teacher = get_object_or_404(Teacher, id=teacher_id)
    if request.method == 'POST':
        form = TeacherSalaryRateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                rate = form.save(commit=False)
                rate.teacher = teacher

                # Close any existing open rate that starts before this one
                open_rates = teacher.salary_rates.filter(
                    valid_to__isnull=True,
                    valid_from__lt=rate.valid_from
                )
                for r in open_rates:
                    # set valid_to to day before new rate starts
                    r.valid_to = rate.valid_from - timezone.timedelta(days=1)
                    r.save(update_fields=['valid_to'])

                rate.save()

                log_audit(
                    actor=request.user,
                    action='UPDATE',
                    entity_type='TeacherSalaryRate',
                    entity_id=rate.id,
                    changes_after={'monthly_amount': str(rate.monthly_amount), 'valid_from': rate.valid_from.isoformat()},
                    reason=f"{teacher.full_name} uchun yangi maosh stavkasi belgilandi"
                )
            messages.success(request, "Yangi oylik stavka muvaffaqiyatli saqlandi.")
    return redirect('academics:teacher_detail', teacher_id=teacher.id)


# --- STUDY GROUPS & SCHEDULES ---

@admin_or_owner_required
def groups_list_view(request):
    groups = StudyGroup.objects.select_related('course', 'teacher').prefetch_related('enrollments').order_by('name')
    return render(request, 'academics/groups_list.html', {'groups': groups})


@admin_or_owner_required
def group_create_view(request):
    if request.method == 'POST':
        form = StudyGroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            log_audit(
                actor=request.user,
                action='CREATE',
                entity_type='StudyGroup',
                entity_id=group.id,
                changes_after={'name': group.name, 'course': group.course.name, 'teacher': group.teacher.full_name},
                reason="Yangi guruh ochildi"
            )
            messages.success(request, f"Guruh '{group.name}' yaratildi.")
            return redirect('academics:group_detail', group_id=group.id)
    else:
        form = StudyGroupForm()

    return render(request, 'academics/group_form.html', {'form': form, 'title': "Yangi guruh ochish"})


@admin_or_owner_required
def group_detail_view(request, group_id):
    group = get_object_or_404(
        StudyGroup.objects.select_related('course', 'teacher').prefetch_related(
            'schedules',
            'enrollments__student',
            'enrollments__price_histories__changed_by',
            'lessons'
        ),
        id=group_id
    )
    schedules = group.schedules.all()
    enrollments = list(group.enrollments.filter(status=Enrollment.Status.ACTIVE).select_related('student'))
    # Payment status is derived automatically from this month's payments made to this group
    from apps.billing.services import get_group_month_payments
    paid_map = get_group_month_payments(group)
    for enr in enrollments:
        paid = paid_map.get(enr.student_id, Decimal('0.00'))
        enr.paid_this_month = paid
        if enr.monthly_price and paid >= enr.monthly_price:
            enr.pay_state = 'paid'
        elif paid > 0:
            enr.pay_state = 'partial'
        else:
            enr.pay_state = 'unpaid'
    recent_lessons = group.lessons.all().order_by('-date')[:10]

    return render(request, 'academics/group_detail.html', {
        'group': group,
        'schedules': schedules,
        'enrollments': enrollments,
        'recent_lessons': recent_lessons,
        'schedule_form': GroupScheduleForm(),
        'multi_schedule_form': GroupScheduleMultiSlotForm(initial={'group': group}),
        'lesson_generate_form': LessonGenerateForm(initial={'group': group}),
        'enrollment_form': EnrollmentForm(initial={'group': group, 'monthly_price': group.course.default_monthly_price}),
    })


@admin_or_owner_required
def group_edit_view(request, group_id):
    group = get_object_or_404(StudyGroup, id=group_id)
    if request.method == 'POST':
        form = StudyGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='StudyGroup',
                entity_id=group.id,
                reason="Guruh ma'lumotlari yangilandi"
            )
            messages.success(request, f"'{group.name}' guruhi yangilandi.")
            return redirect('academics:group_detail', group_id=group.id)
    else:
        form = StudyGroupForm(instance=group)

    return render(request, 'academics/group_form.html', {
        'form': form,
        'title': f"Guruhni tahrirlash: {group.name}",
        'group': group
    })


@admin_or_owner_required
def group_schedule_add_view(request, group_id):
    group = get_object_or_404(StudyGroup, id=group_id)
    if request.method == 'POST':
        form = GroupScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.group = group

            conflicts = check_schedule_conflicts(
                group=group,
                weekday=schedule.weekday,
                start_time=schedule.start_time,
                end_time=schedule.end_time,
                room=schedule.room
            )
            if conflicts:
                for c in conflicts:
                    messages.error(request, f"To'qnashuv: {c}")
                return redirect('academics:group_detail', group_id=group.id)

            schedule.save()
            log_audit(
                actor=request.user,
                action='CREATE',
                entity_type='GroupSchedule',
                entity_id=schedule.id,
                reason=f"{group.name} guruhiga dars jadvali qo'shildi"
            )
            messages.success(request, "Dars jadvali qo'shildi.")
        else:
            for error in form.non_field_errors():
                messages.error(request, error)

    return redirect('academics:group_detail', group_id=group.id)


# --- ENROLLMENT & TRANSFERS ---

@admin_or_owner_required
def enroll_student_view(request, group_id=None):
    initial = {}
    if group_id:
        group = get_object_or_404(StudyGroup, id=group_id)
        initial['group'] = group
        initial['monthly_price'] = group.course.default_monthly_price

    if request.method == 'POST':
        form = EnrollmentForm(request.POST)
        if form.is_valid():
            enrollment = form.save()
            log_audit(
                actor=request.user,
                action='CREATE',
                entity_type='Enrollment',
                entity_id=enrollment.id,
                changes_after={
                    'student': enrollment.student.full_name,
                    'group': enrollment.group.name,
                    'price': str(enrollment.monthly_price)
                },
                reason=f"{enrollment.student.full_name} {enrollment.group.name} guruhiga a'zo qilindi"
            )
            messages.success(request, f"{enrollment.student.full_name} guruhga muvaffaqiyatli a'zo qilindi.")
            return redirect('academics:group_detail', group_id=enrollment.group.id)
    else:
        form = EnrollmentForm(initial=initial)

    return render(request, 'academics/enroll_form.html', {'form': form, 'title': "O'quvchini guruhga a'zo qilish"})


@admin_or_owner_required
def transfer_student_view(request, enrollment_id):
    """
    Transfers a student from one group to another with complete history preservation.
    """
    current_enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    student = current_enrollment.student

    if request.method == 'POST':
        form = TransferEnrollmentForm(request.POST)
        if form.is_valid():
            new_group = form.cleaned_data['new_group']
            transfer_date = form.cleaned_data['transfer_date']
            new_price = form.cleaned_data['new_monthly_price'] or new_group.course.default_monthly_price

            if new_group == current_enrollment.group:
                messages.error(request, "Yangi guruh joriy guruh bilan bir xil bo'lishi mumkin emas.")
                return redirect('academics:group_detail', group_id=current_enrollment.group.id)

            with transaction.atomic():
                # 1. Close current enrollment
                current_enrollment.status = Enrollment.Status.TRANSFERRED
                current_enrollment.end_date = transfer_date
                current_enrollment.save(update_fields=['status', 'end_date'])

                # 2. Create new enrollment
                new_enrollment = Enrollment.objects.create(
                    student=student,
                    group=new_group,
                    start_date=transfer_date,
                    monthly_price=new_price,
                    status=Enrollment.Status.ACTIVE
                )

                log_audit(
                    actor=request.user,
                    action='UPDATE',
                    entity_type='Enrollment',
                    entity_id=new_enrollment.id,
                    changes_before={'group': current_enrollment.group.name},
                    changes_after={'group': new_group.name, 'start_date': transfer_date.isoformat()},
                    reason=f"O'quvchi {current_enrollment.group.name} dan {new_group.name} ga ko'chirildi"
                )

            messages.success(request, f"{student.full_name} '{new_group.name}' guruhiga muvaffaqiyatli ko'chirildi.")
            return redirect('academics:group_detail', group_id=new_group.id)
    else:
        form = TransferEnrollmentForm(initial={'transfer_date': timezone.now().date()})

    return render(request, 'academics/transfer_form.html', {
        'form': form,
        'current_enrollment': current_enrollment,
        'student': student
    })


@admin_or_owner_required
def drop_student_view(request, enrollment_id):
    if request.method == 'POST':
        enrollment = get_object_or_404(Enrollment, id=enrollment_id)
        enrollment.status = Enrollment.Status.DROPPED
        enrollment.end_date = timezone.now().date()
        enrollment.save(update_fields=['status', 'end_date'])

        log_audit(
            actor=request.user,
            action='UPDATE',
            entity_type='Enrollment',
            entity_id=enrollment.id,
            changes_after={'status': 'dropped', 'end_date': enrollment.end_date.isoformat()},
            reason="O'quvchining guruhdagi faoliyati to'xtatildi"
        )
        messages.info(request, f"{enrollment.student.full_name} guruhdan chiqarildi.")
        return redirect('academics:group_detail', group_id=enrollment.group.id)
    return redirect('academics:groups_list')


# ==============================================================================
# INDIVIDUAL PRICING VIEWS (TASK 5)
# ==============================================================================

@admin_or_owner_required
def enrollment_update_price_view(request, enrollment_id):
    """
    Updates the individual monthly tuition fee for a specific student enrollment.
    Logs history and audit trail, and optionally updates current unpaid charge.
    """
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('student', 'group', 'group__course'),
        id=enrollment_id
    )
    redirect_url = request.POST.get('next') or request.GET.get('next') or redirect('academics:group_detail', group_id=enrollment.group.id).url

    if request.method == 'POST':
        form = EnrollmentPriceUpdateForm(request.POST)
        if form.is_valid():
            new_price = form.cleaned_data['monthly_price']
            reason_category = form.cleaned_data['reason_category']
            reason_details = form.cleaned_data.get('reason_details', '').strip()
            category_label = dict(EnrollmentPriceHistory.ReasonCategory.choices).get(reason_category, reason_category)
            full_reason = f"{category_label}: {reason_details}" if reason_details else category_label
            update_unpaid = form.cleaned_data.get('update_current_unpaid_charge', True)

            update_enrollment_price(
                enrollment=enrollment,
                new_price=new_price,
                reason=full_reason,
                user=request.user,
                update_unpaid_current=update_unpaid
            )

            messages.success(
                request,
                f"{enrollment.student.full_name} uchun individual oylik narx muvaffaqiyatli {new_price:,.0f} so'mga o'rnatildi."
            )
            return redirect(redirect_url)
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{field}: {err}")
    else:
        form = EnrollmentPriceUpdateForm(initial={
            'monthly_price': enrollment.monthly_price,
        })

    return render(request, 'academics/enrollment_price_form.html', {
        'enrollment': enrollment,
        'form': form,
        'redirect_url': redirect_url,
    })


@admin_or_owner_required
def enrollment_revert_price_view(request, enrollment_id):
    """
    Reverts an enrollment's individual price back to the standard course price.
    """
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('student', 'group', 'group__course'),
        id=enrollment_id
    )
    redirect_url = request.POST.get('next') or request.GET.get('next') or redirect('academics:group_detail', group_id=enrollment.group.id).url

    if request.method == 'POST':
        revert_enrollment_to_standard_price(
            enrollment=enrollment,
            user=request.user,
            update_unpaid_current=True
        )
        messages.success(
            request,
            f"{enrollment.student.full_name} uchun narx standart kurs narxiga ({enrollment.standard_price:,.0f} so'm) qaytarildi."
        )

    return redirect(redirect_url)


@admin_or_owner_required
def enrollment_price_history_view(request, enrollment_id):
    """
    Displays full audit history of tuition price changes for a student.
    """
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('student', 'group', 'group__course'),
        id=enrollment_id
    )
    history = enrollment.price_histories.select_related('changed_by').order_by('-changed_at')

    return render(request, 'academics/enrollment_price_history.html', {
        'enrollment': enrollment,
        'history': history,
    })


# ==============================================================================
# SCHEDULE SLOTS & LESSON GENERATION (TASK 6)
# ==============================================================================

@admin_or_owner_required
def schedules_list_view(request):
    """
    Central Dars jadvali Hub:
    Lists all schedule slots with filtering, creation, toggling, and generation triggers.
    """
    group_id = request.GET.get('group')
    weekday = request.GET.get('weekday')
    room = request.GET.get('room')
    status_filter = request.GET.get('status') # active / inactive

    qs = GroupSchedule.objects.select_related('group', 'group__course', 'group__teacher').all()

    if group_id:
        qs = qs.filter(group_id=group_id)
    if weekday:
        qs = qs.filter(weekday=weekday)
    if room:
        qs = qs.filter(room__icontains=room)
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    schedules = qs.order_by('weekday', 'start_time')
    groups = StudyGroup.objects.filter(is_active=True).order_by('name')
    rooms = GroupSchedule.objects.exclude(room='').values_list('room', flat=True).distinct()

    return render(request, 'academics/schedules_list.html', {
        'schedules': schedules,
        'groups': groups,
        'rooms': rooms,
        'selected_group': group_id,
        'selected_weekday': weekday,
        'selected_room': room,
        'selected_status': status_filter,
        'weekday_choices': GroupSchedule.Weekday.choices,
        'multi_form': GroupScheduleMultiSlotForm(),
        'generate_form': LessonGenerateForm(),
    })


@admin_or_owner_required
def schedule_slot_create_view(request):
    """
    Creates GroupSchedule slots for one or multiple weekdays.
    Performs conflict detection for teacher, group, and room.
    """
    redirect_url = request.POST.get('next') or request.GET.get('next') or redirect('academics:schedules_list').url

    if request.method == 'POST':
        form = GroupScheduleMultiSlotForm(request.POST)
        if form.is_valid():
            group = form.cleaned_data['group']
            weekdays = form.cleaned_data['weekdays']
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            room = form.cleaned_data.get('room', '')
            is_active = form.cleaned_data.get('is_active', True)

            try:
                slots = create_schedule_slots(
                    group=group,
                    weekdays=weekdays,
                    start_time=start_time,
                    end_time=end_time,
                    room=room,
                    is_active=is_active,
                    user=request.user
                )
                messages.success(request, f"{group.name} uchun {len(slots)} ta dars jadvali sloti muvaffaqiyatli yaratildi.")
                return redirect(redirect_url)
            except Exception as e:
                if hasattr(e, 'messages'):
                    for msg in e.messages:
                        messages.error(request, msg)
                else:
                    messages.error(request, str(e))
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{field}: {err}")

    return redirect(redirect_url)


@admin_or_owner_required
def schedule_slot_edit_view(request, slot_id):
    """
    Edits a single schedule slot with conflict checking.
    """
    slot = get_object_or_404(GroupSchedule.objects.select_related('group'), id=slot_id)
    redirect_url = request.POST.get('next') or request.GET.get('next') or redirect('academics:schedules_list').url

    if request.method == 'POST':
        form = GroupScheduleForm(request.POST, instance=slot)
        if form.is_valid():
            weekday = form.cleaned_data['weekday']
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            room = form.cleaned_data.get('room', '')
            is_active = form.cleaned_data.get('is_active', True)

            conflicts = check_schedule_conflicts(
                group=slot.group,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                room=room,
                exclude_schedule_id=slot.id
            )
            if conflicts:
                for c in conflicts:
                    messages.error(request, f"To'qnashuv: {c}")
                return render(request, 'academics/schedule_slot_form.html', {
                    'slot': slot,
                    'form': form,
                    'redirect_url': redirect_url,
                })

            updated_slot = form.save()
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='GroupSchedule',
                entity_id=updated_slot.id,
                reason=f"Dars jadvali sloti yangilandi ({updated_slot.get_weekday_display()})"
            )
            messages.success(request, "Dars jadvali sloti muvaffaqiyatli yangilandi.")
            return redirect(redirect_url)
    else:
        form = GroupScheduleForm(instance=slot)

    return render(request, 'academics/schedule_slot_form.html', {
        'slot': slot,
        'form': form,
        'redirect_url': redirect_url,
    })


@admin_or_owner_required
def schedule_slot_toggle_view(request, slot_id):
    """
    Toggles schedule slot active / inactive status without deleting it.
    """
    slot = get_object_or_404(GroupSchedule.objects.select_related('group'), id=slot_id)
    redirect_url = request.POST.get('next') or request.GET.get('next') or redirect('academics:schedules_list').url

    if request.method == 'POST':
        slot.is_active = not slot.is_active
        slot.save(update_fields=['is_active'])

        state_str = "faollashtirildi" if slot.is_active else "vaqtincha o'chirildi"
        log_audit(
            actor=request.user,
            action='UPDATE',
            entity_type='GroupSchedule',
            entity_id=slot.id,
            changes_after={'is_active': slot.is_active},
            reason=f"Dars jadvali {state_str}"
        )
        messages.info(request, f"'{slot.group.name}' dars jadvali ({slot.get_weekday_display()}) {state_str}.")

    return redirect(redirect_url)


@admin_or_owner_required
def schedule_slot_delete_view(request, slot_id):
    """
    Deletes a schedule slot with audit logging.
    """
    slot = get_object_or_404(GroupSchedule.objects.select_related('group'), id=slot_id)
    redirect_url = request.POST.get('next') or request.GET.get('next') or redirect('academics:schedules_list').url

    if request.method == 'POST':
        group_name = slot.group.name
        weekday_name = slot.get_weekday_display()
        time_str = f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}"
        slot.delete()

        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='GroupSchedule',
            entity_id=str(slot_id),
            reason=f"{group_name} guruhi uchun {weekday_name} {time_str} jadvali o'chirildi"
        )
        messages.warning(request, f"Dars jadvali sloti ({weekday_name} {time_str}) o'chirildi.")

    return redirect(redirect_url)


@admin_or_owner_required
def generate_lessons_view(request):
    """
    Generates Lessons automatically based on active GroupSchedule slots for a given period.
    Duplicates are skipped without error.
    """
    redirect_url = request.POST.get('next') or request.GET.get('next') or redirect('attendance:lessons_list').url

    if request.method == 'POST':
        form = LessonGenerateForm(request.POST)
        if form.is_valid():
            group = form.cleaned_data.get('group')
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            created_count, skipped_count = generate_lessons_from_schedules(
                group=group,
                start_date=start_date,
                end_date=end_date,
                user=request.user
            )

            group_title = f"'{group.name}' guruhi" if group else "Barcha faol guruhlar"
            messages.success(
                request,
                f"{group_title} uchun {created_count} ta yangi dars shakllantirildi ({skipped_count} ta avvaldan mavjud dars o'tkazib yuborildi)."
            )
            return redirect(redirect_url)
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{field}: {err}")

    return redirect(redirect_url)


# 8 distinct aesthetic group colors for calendar
CALENDAR_PALETTE = [
    {'bg': '#e0f2fe', 'border': '#0284c7', 'text': '#0369a1', 'badge': 'bg-primary-subtle text-primary border-primary'},
    {'bg': '#dcfce7', 'border': '#16a34a', 'text': '#15803d', 'badge': 'bg-success-subtle text-success border-success'},
    {'bg': '#f3e8ff', 'border': '#9333ea', 'text': '#7e22ce', 'badge': 'bg-purple-subtle text-purple border-purple'},
    {'bg': '#ffedd5', 'border': '#ea580c', 'text': '#c2410c', 'badge': 'bg-warning-subtle text-warning-emphasis border-warning'},
    {'bg': '#ccfbf1', 'border': '#0d9488', 'text': '#0f766e', 'badge': 'bg-info-subtle text-info-emphasis border-info'},
    {'bg': '#ffe4e6', 'border': '#e11d48', 'text': '#be123c', 'badge': 'bg-danger-subtle text-danger border-danger'},
    {'bg': '#fef9c3', 'border': '#ca8a04', 'text': '#a16207', 'badge': 'bg-warning-subtle text-dark border-warning'},
    {'bg': '#e0e7ff', 'border': '#4f46e5', 'text': '#4338ca', 'badge': 'bg-indigo-subtle text-indigo border-indigo'},
]


def get_group_color(group_id: int):
    return CALENDAR_PALETTE[(group_id or 0) % len(CALENDAR_PALETTE)]


@admin_or_owner_required
def schedule_calendar_view(request):
    """
    Interactive Schedule & Lessons Calendar with 3 view modes:
    - 'month': Full month grid view with lesson cards
    - 'week': 7-day weekly column view with time intervals
    - 'rooms': Room occupancy view
    With filtering by Group, Teacher, and Room.
    """
    mode = request.GET.get('mode', 'month')
    if mode not in ['month', 'week', 'rooms']:
        mode = 'month'

    today = timezone.now().date()

    # Filters
    group_id = request.GET.get('group')
    teacher_id = request.GET.get('teacher')
    room_filter = request.GET.get('room')

    # Year & Month parsing
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month

    # Clamp month
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    current_month_date = date(year, month, 1)

    # Next / Prev month navigation
    prev_month_date = (current_month_date - timedelta(days=1)).replace(day=1)
    next_month_date = (current_month_date + timedelta(days=32)).replace(day=1)

    # Base Query for Lessons
    lessons_qs = Lesson.objects.select_related(
        'group', 'group__course', 'group__teacher'
    ).prefetch_related('attendances')

    if group_id:
        lessons_qs = lessons_qs.filter(group_id=group_id)
    if teacher_id:
        lessons_qs = lessons_qs.filter(group__teacher_id=teacher_id)
    if room_filter:
        lessons_qs = lessons_qs.filter(room__icontains=room_filter)

    groups = StudyGroup.objects.filter(is_active=True).order_by('name')
    teachers = Teacher.objects.filter(status=Teacher.Status.ACTIVE).order_by('full_name')
    rooms = list(GroupSchedule.objects.exclude(room='').values_list('room', flat=True).distinct())

    # Build View Data depending on mode
    calendar_data = {}

    if mode == 'month':
        # Month range
        _, total_days = calendar.monthrange(year, month)
        m_start = date(year, month, 1)
        m_end = date(year, month, total_days)

        month_lessons = lessons_qs.filter(date__gte=m_start, date__lte=m_end).order_by('starts_at')

        # Index lessons by date
        lessons_by_date = {}
        for l in month_lessons:
            l.color_scheme = get_group_color(l.group_id)
            if l.date not in lessons_by_date:
                lessons_by_date[l.date] = []
            lessons_by_date[l.date].append(l)

        # Build grid with calendar.Calendar(firstweekday=0) -> Monday=0
        cal = calendar.Calendar(firstweekday=0)
        weeks = []
        for week in cal.monthdatescalendar(year, month):
            week_days = []
            for d in week:
                week_days.append({
                    'date': d,
                    'is_current_month': d.month == month,
                    'is_today': d == today,
                    'lessons': lessons_by_date.get(d, []),
                })
            weeks.append(week_days)

        calendar_data['weeks'] = weeks

    elif mode == 'week':
        # Selected week date (defaults to today or date in current month)
        date_str = request.GET.get('date')
        if date_str:
            try:
                base_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                base_date = today
        else:
            base_date = today

        # Find Monday of that week
        week_start = base_date - timedelta(days=base_date.weekday())
        week_end = week_start + timedelta(days=6)

        week_lessons = lessons_qs.filter(date__gte=week_start, date__lte=week_end).order_by('starts_at')
        lessons_by_date = {}
        for l in week_lessons:
            l.color_scheme = get_group_color(l.group_id)
            if l.date not in lessons_by_date:
                lessons_by_date[l.date] = []
            lessons_by_date[l.date].append(l)

        days_data = []
        curr = week_start
        while curr <= week_end:
            days_data.append({
                'date': curr,
                'weekday_name': curr.strftime('%A'),
                'is_today': curr == today,
                'lessons': lessons_by_date.get(curr, []),
            })
            curr += timedelta(days=1)

        calendar_data['week_days'] = days_data
        calendar_data['week_start'] = week_start
        calendar_data['week_end'] = week_end
        calendar_data['prev_week_date'] = week_start - timedelta(days=7)
        calendar_data['next_week_date'] = week_start + timedelta(days=7)

    elif mode == 'rooms':
        # Rooms occupancy mode for target date
        date_str = request.GET.get('date')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = today
        else:
            target_date = today

        day_lessons = lessons_qs.filter(date=target_date).order_by('starts_at')
        rooms_map = {}
        for r in rooms:
            rooms_map[r] = []

        unassigned_lessons = []
        for l in day_lessons:
            l.color_scheme = get_group_color(l.group_id)
            if l.room and l.room in rooms_map:
                rooms_map[l.room].append(l)
            elif l.room:
                if l.room not in rooms_map:
                    rooms_map[l.room] = []
                rooms_map[l.room].append(l)
            else:
                unassigned_lessons.append(l)

        calendar_data['target_date'] = target_date
        calendar_data['rooms_map'] = rooms_map
        calendar_data['unassigned_lessons'] = unassigned_lessons
        calendar_data['prev_day'] = target_date - timedelta(days=1)
        calendar_data['next_day'] = target_date + timedelta(days=1)

    return render(request, 'academics/schedule_calendar.html', {
        'mode': mode,
        'year': year,
        'month': month,
        'current_month_date': current_month_date,
        'prev_month_date': prev_month_date,
        'next_month_date': next_month_date,
        'today': today,
        'calendar_data': calendar_data,
        'groups': groups,
        'teachers': teachers,
        'rooms': rooms,
        'selected_group': group_id,
        'selected_teacher': teacher_id,
        'selected_room': room_filter,
        'multi_form': GroupScheduleMultiSlotForm(),
        'generate_form': LessonGenerateForm(),
    })
