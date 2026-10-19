from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from apps.accounts.decorators import admin_or_owner_required
from apps.audit.services import log_audit
from .models import Student
from .forms import StudentForm


@admin_or_owner_required
def students_list_view(request):
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'active')

    students = Student.objects.all().prefetch_related('enrollments__group')

    if q:
        students = students.filter(
            Q(full_name__icontains=q) |
            Q(phone__icontains=q) |
            Q(parent_phone__icontains=q)
        )

    if status_filter and status_filter != 'all':
        students = students.filter(status=status_filter)

    return render(request, 'students/students_list.html', {
        'students': students,
        'q': q,
        'status_filter': status_filter,
        'status_choices': Student.Status.choices,
    })


@admin_or_owner_required
def student_create_view(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            log_audit(
                actor=request.user,
                action='CREATE',
                entity_type='Student',
                entity_id=student.id,
                changes_after={'full_name': student.full_name, 'phone': student.phone},
                reason="Yangi o'quvchi ro'yxatdan o'tkazildi"
            )
            messages.success(request, f"O'quvchi '{student.full_name}' muvaffaqiyatli saqlandi.")
            return redirect('students:student_detail', student_id=student.id)
    else:
        form = StudentForm()

    return render(request, 'students/student_form.html', {'form': form, 'title': "Yangi o'quvchi qo'shish"})


@admin_or_owner_required
def student_detail_view(request, student_id):
    student = get_object_or_404(
        Student.objects.prefetch_related(
            'enrollments__group__course',
            'enrollments__group__teacher',
            'monthly_charges__allocations',
            'payments__allocations',
            'attendances__lesson__group'
        ),
        id=student_id
    )

    charges = student.monthly_charges.all().order_by('-billing_month')
    payments = student.payments.all().order_by('-paid_at')
    enrollments = student.enrollments.all().order_by('-created_at')
    attendances = student.attendances.all().select_related('lesson', 'lesson__group').order_by('-lesson__date')[:15]

    return render(request, 'students/student_detail.html', {
        'student': student,
        'charges': charges,
        'payments': payments,
        'enrollments': enrollments,
        'attendances': attendances,
    })


@admin_or_owner_required
def student_edit_view(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    old_data = {'full_name': student.full_name, 'phone': student.phone, 'status': student.status}

    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            updated_student = form.save()
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='Student',
                entity_id=student.id,
                changes_before=old_data,
                changes_after={'full_name': updated_student.full_name, 'phone': updated_student.phone, 'status': updated_student.status},
                reason="O'quvchi ma'lumotlari tahrirlandi"
            )
            messages.success(request, "O'quvchi ma'lumotlari yangilandi.")
            return redirect('students:student_detail', student_id=student.id)
    else:
        form = StudentForm(instance=student)

    return render(request, 'students/student_form.html', {
        'form': form,
        'title': f"O'quvchini tahrirlash: {student.full_name}",
        'student': student
    })


@admin_or_owner_required
def student_archive_view(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(Student, id=student_id)
        student.status = Student.Status.ARCHIVED
        student.save(update_fields=['status'])
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='Student',
            entity_id=student.id,
            changes_after={'status': 'archived'},
            reason="O'quvchi arxivga o'tkazildi"
        )
        messages.warning(request, f"O'quvchi '{student.full_name}' arxivlandi.")
    return redirect('students:students_list')


@admin_or_owner_required
def student_restore_view(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(Student, id=student_id)
        student.status = Student.Status.ACTIVE
        student.save(update_fields=['status'])
        log_audit(
            actor=request.user,
            action='STATUS_CHANGE',
            entity_type='Student',
            entity_id=student.id,
            changes_after={'status': 'active'},
            reason="O'quvchi arxivdan faol holatga qaytarildi"
        )
        messages.success(request, f"O'quvchi '{student.full_name}' faollashtirildi.")
    return redirect('students:student_detail', student_id=student.id)
