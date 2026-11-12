from django.http import JsonResponse
from django.db.models import Q
from django.urls import reverse
from apps.accounts.decorators import admin_or_owner_required
from apps.students.models import Student
from apps.academics.models import Teacher, Enrollment


@admin_or_owner_required
def search_students_api(request):
    """
    Dynamic search endpoint for students.
    Requires at least 3 characters.
    Searches by first name, last name, phone.
    Works efficiently with large record counts (indexed and limited).
    """
    q = request.GET.get('q', '').strip()
    if len(q) < 3:
        return JsonResponse({
            'results': [],
            'message': 'Kamida 3 ta harf kiriting'
        })

    terms = q.split()
    qs = Student.objects.all()
    for term in terms:
        qs = qs.filter(
            Q(full_name__icontains=term) |
            Q(phone__icontains=term) |
            Q(parent_phone__icontains=term)
        )

    qs = qs.order_by('full_name')[:30]

    results = []
    for s in qs:
        results.append({
            'id': s.id,
            'text': f"{s.full_name} ({s.phone})",
            'full_name': s.full_name,
            'phone': s.phone,
            'status': s.get_status_display(),
            'detail_url': reverse('students:student_detail', args=[s.id]),
        })

    return JsonResponse({'results': results})


@admin_or_owner_required
def search_teachers_api(request):
    """
    Dynamic search endpoint for teachers.
    Requires at least 3 characters.
    Searches by first name, last name, phone, specialization.
    Works efficiently with large record counts (indexed and limited).
    """
    q = request.GET.get('q', '').strip()
    if len(q) < 3:
        return JsonResponse({
            'results': [],
            'message': 'Kamida 3 ta harf kiriting'
        })

    terms = q.split()
    qs = Teacher.objects.all()
    for term in terms:
        qs = qs.filter(
            Q(full_name__icontains=term) |
            Q(phone__icontains=term) |
            Q(specialization__icontains=term)
        )

    qs = qs.order_by('full_name')[:30]

    results = []
    for t in qs:
        spec_text = f" ({t.specialization})" if t.specialization else f" ({t.phone})"
        results.append({
            'id': t.id,
            'text': f"{t.full_name}{spec_text}",
            'full_name': t.full_name,
            'phone': t.phone,
            'specialization': t.specialization or '',
            'status': t.get_status_display(),
            'detail_url': reverse('academics:teacher_detail', args=[t.id]),
        })

    return JsonResponse({'results': results})


@admin_or_owner_required
def search_enrollments_api(request):
    """
    Dynamic search endpoint for active student enrollments (used in charges, etc.).
    Requires at least 3 characters.
    """
    q = request.GET.get('q', '').strip()
    if len(q) < 3:
        return JsonResponse({
            'results': [],
            'message': 'Kamida 3 ta harf kiriting'
        })

    terms = q.split()
    qs = Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).select_related('student', 'group')
    for term in terms:
        qs = qs.filter(
            Q(student__full_name__icontains=term) |
            Q(student__phone__icontains=term) |
            Q(group__name__icontains=term)
        )

    qs = qs.order_by('student__full_name')[:30]

    results = []
    for enr in qs:
        results.append({
            'id': enr.id,
            'text': f"{enr.student.full_name} — {enr.group.name} ({enr.monthly_price:.0f} so'm)",
            'student_name': enr.student.full_name,
            'group_name': enr.group.name,
            'monthly_price': str(enr.monthly_price),
            'detail_url': reverse('students:student_detail', args=[enr.student.id]),
        })

    return JsonResponse({'results': results})


@admin_or_owner_required
def search_universal_api(request):
    """
    Universal search across both students and teachers.
    Used in navbar across all sections of CRM.
    """
    q = request.GET.get('q', '').strip()
    if len(q) < 3:
        return JsonResponse({
            'students': [],
            'teachers': [],
            'total': 0,
            'message': 'Kamida 3 ta harf kiriting'
        })

    terms = q.split()

    # Search students
    sqs = Student.objects.all()
    for term in terms:
        sqs = sqs.filter(
            Q(full_name__icontains=term) |
            Q(phone__icontains=term)
        )
    student_matches = sqs.prefetch_related('enrollments__group').order_by('full_name')[:8]

    students = []
    for s in student_matches:
        active_groups = [e.group.name for e in s.enrollments.all() if e.status == 'active']
        students.append({
            'id': s.id,
            'full_name': s.full_name,
            'phone': s.phone,
            'status': s.get_status_display(),
            'active_groups': active_groups,
            'url': reverse('students:student_detail', args=[s.id]),
        })

    # Search teachers
    tqs = Teacher.objects.all()
    for term in terms:
        tqs = tqs.filter(
            Q(full_name__icontains=term) |
            Q(phone__icontains=term) |
            Q(specialization__icontains=term)
        )
    teacher_matches = tqs.prefetch_related('groups').order_by('full_name')[:8]

    teachers = []
    for t in teacher_matches:
        teachers.append({
            'id': t.id,
            'full_name': t.full_name,
            'phone': t.phone,
            'specialization': t.specialization or '',
            'groups_count': t.groups.count(),
            'status': t.get_status_display(),
            'url': reverse('academics:teacher_detail', args=[t.id]),
        })

    return JsonResponse({
        'students': students,
        'teachers': teachers,
        'total': len(students) + len(teachers),
    })
