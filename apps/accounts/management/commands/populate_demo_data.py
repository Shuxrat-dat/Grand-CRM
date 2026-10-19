from datetime import date, time
from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.accounts.models import User, CenterSettings
from apps.students.models import Student
from apps.academics.models import Course, Teacher, TeacherSalaryRate, StudyGroup, GroupSchedule, Enrollment
from apps.attendance.models import Lesson, AttendanceRecord
from apps.billing.models import MonthlyCharge, Payment, PaymentAllocation
from apps.payroll.models import SalaryRecord, SalaryPayment
from apps.finance.models import Expense
from apps.billing.services import register_payment, generate_monthly_charge


class Command(BaseCommand):
    help = "Populates test / demo data for local exploration and verification"

    def handle(self, *args, **options):
        # 1. Admin user
        admin_user, _ = User.objects.get_or_create(username='admin')
        admin_user.role = User.Role.ADMIN
        admin_user.is_staff = False
        admin_user.first_name = "Aziza"
        admin_user.last_name = "Karimova"
        admin_user.set_password('admin123')
        admin_user.save()

        # 2. Courses
        c_ielts, _ = Course.objects.get_or_create(
            name="General English & IELTS",
            defaults={'default_monthly_price': Decimal('500000.00'), 'duration_months': 6, 'description': "IELTS 7+ tayyorlov kursi"}
        )
        c_math, _ = Course.objects.get_or_create(
            name="Matematika (DTM va Milliy sertifikat)",
            defaults={'default_monthly_price': Decimal('450000.00'), 'duration_months': 9, 'description': "Abituriyentlar uchun matematika"}
        )

        # 3. Teachers & Rates
        t1, _ = Teacher.objects.get_or_create(
            full_name="Jamshid Ergashev",
            defaults={'phone': "+998901112233", 'specialization': "IELTS Instructor (Band 8.5)", 'hire_date': date(2026, 1, 1)}
        )
        TeacherSalaryRate.objects.get_or_create(
            teacher=t1,
            monthly_amount=Decimal('4500000.00'),
            valid_from=date(2026, 1, 1)
        )

        t2, _ = Teacher.objects.get_or_create(
            full_name="Shahzoda Rahimova",
            defaults={'phone': "+998902223344", 'specialization': "Oliy toifali matematika o'qituvchisi", 'hire_date': date(2026, 1, 1)}
        )
        TeacherSalaryRate.objects.get_or_create(
            teacher=t2,
            monthly_amount=Decimal('4000000.00'),
            valid_from=date(2026, 1, 1)
        )

        # 4. Groups
        g1, _ = StudyGroup.objects.get_or_create(
            name="IELTS Intensive (09:00)",
            defaults={'course': c_ielts, 'teacher': t1, 'capacity': 14, 'start_date': date(2026, 10, 1)}
        )
        GroupSchedule.objects.get_or_create(
            group=g1, weekday=1, start_time=time(9, 0), end_time=time(10, 30), defaults={'room': "1-auditoriya"}
        )
        GroupSchedule.objects.get_or_create(
            group=g1, weekday=3, start_time=time(9, 0), end_time=time(10, 30), defaults={'room': "1-auditoriya"}
        )
        GroupSchedule.objects.get_or_create(
            group=g1, weekday=5, start_time=time(9, 0), end_time=time(10, 30), defaults={'room': "1-auditoriya"}
        )

        # 5. Students & Enrollments
        s1, _ = Student.objects.get_or_create(
            full_name="Ulug'bek Nazarov",
            defaults={'phone': "+998901234501", 'parent_phone': "+998901234502", 'joined_at': date(2026, 10, 1)}
        )
        enr1, _ = Enrollment.objects.get_or_create(
            student=s1, group=g1, defaults={'start_date': date(2026, 10, 1), 'monthly_price': Decimal('500000.00')}
        )

        s2, _ = Student.objects.get_or_create(
            full_name="Gulnoza Ahmedova",
            defaults={'phone': "+998901234503", 'parent_phone': "+998901234504", 'joined_at': date(2026, 10, 1)}
        )
        enr2, _ = Enrollment.objects.get_or_create(
            student=s2, group=g1, defaults={'start_date': date(2026, 10, 1), 'monthly_price': Decimal('500000.00')}
        )

        # 6. Charges & Payments for current month
        try:
            ch1 = generate_monthly_charge(enrollment_id=enr1.id, billing_month=date(2026, 10, 1), user=admin_user)
            register_payment(student_id=s1.id, amount=Decimal('500000.00'), method='cash', reference='CH-001', user=admin_user)
        except Exception:
            pass

        try:
            ch2 = generate_monthly_charge(enrollment_id=enr2.id, billing_month=date(2026, 10, 1), user=admin_user)
            register_payment(student_id=s2.id, amount=Decimal('200000.00'), method='card', reference='TR-9901', user=admin_user)
        except Exception:
            pass

        # 7. Lessons & Attendance
        l1, _ = Lesson.objects.get_or_create(
            group=g1, date=date(2026, 10, 19), starts_at=time(9, 0), ends_at=time(10, 30),
            defaults={'topic': "Reading: Matching headings & skimming", 'status': Lesson.Status.COMPLETED}
        )
        AttendanceRecord.objects.get_or_create(lesson=l1, student=s1, defaults={'status': AttendanceRecord.Status.PRESENT})
        AttendanceRecord.objects.get_or_create(lesson=l1, student=s2, defaults={'status': AttendanceRecord.Status.PRESENT})

        # 8. Operational Expense
        Expense.objects.get_or_create(
            description="Markaz xonalari uchun oylik bino ijarasi",
            defaults={'category': 'rent', 'amount': Decimal('3500000.00'), 'occurred_at': date(2026, 10, 5), 'method': 'bank_transfer'}
        )

        self.stdout.write(self.style.SUCCESS(
            "Demo ma'lumotlar muvaffaqiyatli yuklandi!\n"
            "- Admin hisobi: admin / admin123\n"
            "- Ega hisobi: owner / owner123\n"
            "- Kurslar, o'qituvchilar, guruhlar, o'quvchilar va darslar tayyorlandi."
        ))
