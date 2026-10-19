from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from apps.accounts.decorators import admin_or_owner_required, owner_required
from apps.audit.services import log_audit
from .models import Course, Teacher, TeacherSalaryRate, StudyGroup, GroupSchedule, Enrollment
from .forms import (
    CourseForm, TeacherForm, TeacherSalaryRateForm,
    StudyGroupForm, GroupScheduleForm, EnrollmentForm, TransferEnrollmentForm
)
from apps.students.models import Student


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
            'lessons'
        ),
        id=group_id
    )
    schedules = group.schedules.all()
    enrollments = group.enrollments.filter(status=Enrollment.Status.ACTIVE).select_related('student')
    recent_lessons = group.lessons.all().order_by('-date')[:10]

    return render(request, 'academics/group_detail.html', {
        'group': group,
        'schedules': schedules,
        'enrollments': enrollments,
        'recent_lessons': recent_lessons,
        'schedule_form': GroupScheduleForm(),
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

            # Conflict checking: check if room or teacher has overlapping schedule
            overlapping_room = GroupSchedule.objects.filter(
                weekday=schedule.weekday,
                room=schedule.room,
                start_time__lt=schedule.end_time,
                end_time__gt=schedule.start_time
            ).exclude(group=group).exists()

            overlapping_teacher = GroupSchedule.objects.filter(
                group__teacher=group.teacher,
                weekday=schedule.weekday,
                start_time__lt=schedule.end_time,
                end_time__gt=schedule.start_time
            ).exclude(group=group).exists()

            if overlapping_room and schedule.room:
                messages.warning(request, f"Diqqat: '{schedule.room}' xonasida belgilangan vaqt oralig'ida boshqa guruh darsi mavjud!")
            if overlapping_teacher:
                messages.warning(request, f"Diqqat: O'qituvchi {group.teacher.full_name} ushbu vaqtda boshqa guruhda darsi bor!")

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
