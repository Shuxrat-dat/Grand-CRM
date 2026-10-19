from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.accounts.models import User
from apps.students.models import Student
from apps.academics.models import Course, Teacher, TeacherSalaryRate, StudyGroup, Enrollment
from apps.billing.models import MonthlyCharge, Payment, PaymentAllocation


class AcademicsAndStudentsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin_staff', password='pwd', role=User.Role.ADMIN)
        self.course = Course.objects.create(
            name='Ingliz tili IELTS',
            default_monthly_price=Decimal('600000.00'),
            duration_months=3
        )
        self.teacher = Teacher.objects.create(
            full_name='Ali Valiyev',
            phone='+998901112233',
            hire_date=date(2026, 1, 1)
        )
        self.group = StudyGroup.objects.create(
            name='IELTS 1',
            course=self.course,
            teacher=self.teacher,
            capacity=12,
            start_date=date(2026, 1, 1)
        )

    def test_student_creation_and_enrollment(self):
        """3. Student creation and group enrollment with individual price snapshot."""
        student = Student.objects.create(
            full_name='Jasur Rashidov',
            phone='+998909998877',
            joined_at=date(2026, 1, 10),
            status=Student.Status.ACTIVE
        )

        enrollment = Enrollment.objects.create(
            student=student,
            group=self.group,
            start_date=date(2026, 1, 10),
            monthly_price=Decimal('550000.00'), # individual discounted price
            status=Enrollment.Status.ACTIVE
        )

        self.assertEqual(enrollment.student, student)
        self.assertEqual(enrollment.group, self.group)
        self.assertEqual(enrollment.monthly_price, Decimal('550000.00'))

        # Course default price changed later should NOT alter enrollment snapshot
        self.course.default_monthly_price = Decimal('700000.00')
        self.course.save()
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.monthly_price, Decimal('550000.00'))

    def test_student_archiving_preserves_history(self):
        """16. Student archiving preserves complete financial and academic history."""
        student = Student.objects.create(
            full_name='Botir Zokirov',
            phone='+998901234567',
            joined_at=date(2026, 1, 1)
        )
        enrollment = Enrollment.objects.create(
            student=student,
            group=self.group,
            start_date=date(2026, 1, 1),
            monthly_price=Decimal('600000.00')
        )
        charge = MonthlyCharge.objects.create(
            student=student,
            enrollment=enrollment,
            billing_month=date(2026, 1, 1),
            amount=Decimal('600000.00'),
            due_date=date(2026, 1, 5),
            status=MonthlyCharge.Status.PAID
        )
        payment = Payment.objects.create(
            student=student,
            amount=Decimal('600000.00'),
            method=Payment.Method.CASH,
            status=Payment.Status.COMPLETED
        )
        PaymentAllocation.objects.create(
            payment=payment,
            charge=charge,
            amount=Decimal('600000.00')
        )

        # Archive the student
        student.status = Student.Status.ARCHIVED
        student.save(update_fields=['status'])

        # Verify historical records remain fully preserved and queryable
        student.refresh_from_db()
        self.assertEqual(student.status, Student.Status.ARCHIVED)
        self.assertEqual(student.monthly_charges.count(), 1)
        self.assertEqual(student.payments.count(), 1)
        self.assertEqual(student.total_charged, Decimal('600000.00'))
        self.assertEqual(student.total_payments_received, Decimal('600000.00'))
        self.assertEqual(student.total_debt, Decimal('0.00'))
