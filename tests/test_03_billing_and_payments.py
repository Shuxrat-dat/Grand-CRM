import uuid
import threading
from decimal import Decimal
from datetime import date
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.db import connection

from apps.accounts.models import User, CenterSettings
from apps.students.models import Student
from apps.academics.models import Course, Teacher, StudyGroup, Enrollment
from apps.billing.models import MonthlyCharge, Payment, PaymentAllocation
from apps.billing.services import (
    generate_monthly_charge, register_payment, cancel_payment, cancel_charge
)


class BillingAndPaymentsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin_billing', password='pwd', role=User.Role.ADMIN)
        self.course = Course.objects.create(
            name='Matematika',
            default_monthly_price=Decimal('500000.00'),
            duration_months=6
        )
        self.teacher = Teacher.objects.create(
            full_name='Zafar Usmonov',
            phone='+998901234567',
            hire_date=date(2026, 1, 1)
        )
        self.group = StudyGroup.objects.create(
            name='Algebra 1',
            course=self.course,
            teacher=self.teacher,
            capacity=15,
            start_date=date(2026, 1, 1)
        )
        self.student = Student.objects.create(
            full_name='Dilshod Karimov',
            phone='+998907778899',
            joined_at=date(2026, 1, 1)
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            group=self.group,
            start_date=date(2026, 1, 1),
            monthly_price=Decimal('500000.00')
        )

    def test_monthly_charge_generation_and_proration(self):
        """4. Generation of monthly charge with Full Month and Proportional policy."""
        # 4a. Full month
        charge_jan = generate_monthly_charge(
            enrollment_id=self.enrollment.id,
            billing_month=date(2026, 1, 1),
            proration_policy=CenterSettings.ProrationPolicy.FULL_MONTH,
            user=self.user
        )
        self.assertEqual(charge_jan.amount, Decimal('500000.00'))
        self.assertIn(charge_jan.status, [MonthlyCharge.Status.UNPAID, MonthlyCharge.Status.OVERDUE])
        self.assertEqual(self.student.total_debt, Decimal('500000.00'))

        # 4b. Mid-month student joining with proportional calculation
        student_mid = Student.objects.create(
            full_name='Sardor Kamilov',
            phone='+998903332211',
            joined_at=date(2026, 2, 15)
        )
        enr_mid = Enrollment.objects.create(
            student=student_mid,
            group=self.group,
            start_date=date(2026, 2, 15), # starts in middle of February (Feb has 28 days)
            monthly_price=Decimal('560000.00')
        )
        # Active days: Feb 15 to Feb 28 = 14 days out of 28 => exactly 50% = 280,000
        charge_feb = generate_monthly_charge(
            enrollment_id=enr_mid.id,
            billing_month=date(2026, 2, 1),
            proration_policy=CenterSettings.ProrationPolicy.PROPORTIONAL,
            user=self.user
        )
        self.assertEqual(charge_feb.amount, Decimal('280000.00'))

    def test_partial_payment_and_debt_recalculation(self):
        """5. Partial payment and accurate debt recalculation."""
        charge = generate_monthly_charge(
            enrollment_id=self.enrollment.id,
            billing_month=date(2026, 1, 1),
            user=self.user
        )
        self.assertEqual(self.student.total_debt, Decimal('500000.00'))

        # Pay 200,000 out of 500,000
        payment = register_payment(
            student_id=self.student.id,
            amount=Decimal('200000.00'),
            method=Payment.Method.CASH,
            user=self.user
        )

        charge.refresh_from_db()
        self.assertEqual(charge.status, MonthlyCharge.Status.PARTIAL)
        self.assertEqual(charge.allocated_amount, Decimal('200000.00'))
        self.assertEqual(charge.remaining_balance, Decimal('300000.00'))
        self.assertEqual(self.student.total_debt, Decimal('300000.00'))
        self.assertEqual(payment.unallocated_amount, Decimal('0.00'))

    def test_full_payment(self):
        """6. Full payment settles debt and marks charge paid."""
        charge = generate_monthly_charge(
            enrollment_id=self.enrollment.id,
            billing_month=date(2026, 1, 1),
            user=self.user
        )

        payment = register_payment(
            student_id=self.student.id,
            amount=Decimal('500000.00'),
            method=Payment.Method.CARD,
            user=self.user
        )

        charge.refresh_from_db()
        self.assertEqual(charge.status, MonthlyCharge.Status.PAID)
        self.assertEqual(charge.remaining_balance, Decimal('0.00'))
        self.assertEqual(self.student.total_debt, Decimal('0.00'))
        self.assertEqual(self.student.prepayment_balance, Decimal('0.00'))

    def test_past_debt_payment_fifo(self):
        """7. Payment automatically covers past month debt first (FIFO)."""
        # January charge
        charge_jan = generate_monthly_charge(
            enrollment_id=self.enrollment.id,
            billing_month=date(2026, 1, 1),
            user=self.user
        )
        # February charge
        charge_feb = generate_monthly_charge(
            enrollment_id=self.enrollment.id,
            billing_month=date(2026, 2, 1),
            user=self.user
        )

        self.assertEqual(self.student.total_debt, Decimal('1000000.00'))

        # Pay 600,000: should cover 500,000 of Jan (oldest) and 100,000 of Feb
        payment = register_payment(
            student_id=self.student.id,
            amount=Decimal('600000.00'),
            method=Payment.Method.BANK_TRANSFER,
            user=self.user
        )

        charge_jan.refresh_from_db()
        charge_feb.refresh_from_db()

        self.assertEqual(charge_jan.status, MonthlyCharge.Status.PAID)
        self.assertEqual(charge_jan.remaining_balance, Decimal('0.00'))

        self.assertEqual(charge_feb.status, MonthlyCharge.Status.PARTIAL)
        self.assertEqual(charge_feb.allocated_amount, Decimal('100000.00'))
        self.assertEqual(charge_feb.remaining_balance, Decimal('400000.00'))

        self.assertEqual(self.student.total_debt, Decimal('400000.00'))

    def test_overpayment_and_prepayment_balance(self):
        """8. Overpayment: excess stays as prepayment and auto-allocates to future charge."""
        charge_jan = generate_monthly_charge(
            enrollment_id=self.enrollment.id,
            billing_month=date(2026, 1, 1),
            user=self.user
        )

        # Student pays 800,000 for a 500,000 charge
        payment = register_payment(
            student_id=self.student.id,
            amount=Decimal('800000.00'),
            method=Payment.Method.CASH,
            user=self.user
        )

        charge_jan.refresh_from_db()
        self.assertEqual(charge_jan.status, MonthlyCharge.Status.PAID)
        self.assertEqual(payment.allocated_amount, Decimal('500000.00'))
        self.assertEqual(payment.unallocated_amount, Decimal('300000.00'))
        self.assertEqual(self.student.total_debt, Decimal('0.00'))
        self.assertEqual(self.student.prepayment_balance, Decimal('300000.00'))

        # Next month charge is generated: should automatically consume the 300,000 prepayment!
        charge_feb = generate_monthly_charge(
            enrollment_id=self.enrollment.id,
            billing_month=date(2026, 2, 1),
            user=self.user
        )

        charge_feb.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(charge_feb.allocated_amount, Decimal('300000.00'))
        self.assertEqual(charge_feb.remaining_balance, Decimal('200000.00'))
        self.assertEqual(charge_feb.status, MonthlyCharge.Status.PARTIAL)
        self.assertEqual(payment.unallocated_amount, Decimal('0.00'))
        self.assertEqual(self.student.total_debt, Decimal('200000.00'))

    def test_idempotency_protection(self):
        """9. Idempotency key prevents duplicate payments on retried network requests."""
        key = str(uuid.uuid4())

        pay1 = register_payment(
            student_id=self.student.id,
            amount=Decimal('500000.00'),
            method=Payment.Method.CARD,
            user=self.user,
            idempotency_key=key
        )

        # Repeated request with same idempotency key
        pay2 = register_payment(
            student_id=self.student.id,
            amount=Decimal('500000.00'),
            method=Payment.Method.CARD,
            user=self.user,
            idempotency_key=key
        )

        # Must return same payment instance, no new payment row created
        self.assertEqual(pay1.id, pay2.id)
        self.assertEqual(Payment.objects.filter(idempotency_key=key).count(), 1)

    def test_payment_cancellation_and_storno(self):
        """10. Payment cancellation (storno) resets charge statuses and restores debt."""
        charge = generate_monthly_charge(
            enrollment_id=self.enrollment.id,
            billing_month=date(2026, 1, 1),
            user=self.user
        )

        payment = register_payment(
            student_id=self.student.id,
            amount=Decimal('500000.00'),
            method=Payment.Method.CASH,
            user=self.user
        )
        charge.refresh_from_db()
        self.assertEqual(charge.status, MonthlyCharge.Status.PAID)

        # Cancel payment (Storno)
        cancel_payment(payment_id=payment.id, user=self.user, reason="Xato kiritilgan chek")

        payment.refresh_from_db()
        charge.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.CANCELLED)
        self.assertIn(charge.status, [MonthlyCharge.Status.UNPAID, MonthlyCharge.Status.OVERDUE])
        self.assertEqual(charge.allocated_amount, Decimal('0.00'))
        self.assertEqual(charge.remaining_balance, Decimal('500000.00'))
        self.assertEqual(self.student.total_debt, Decimal('500000.00'))


class ConcurrentFinancialOperationsTest(TransactionTestCase):
    """17. Concurrent financial operations test."""
    def test_concurrent_payments_allocation_integrity(self):
        user = User.objects.create_user(username='concurrent_user', password='pwd')
        course = Course.objects.create(name='Fizika', default_monthly_price=Decimal('500000.00'))
        teacher = Teacher.objects.create(full_name='Rustam', phone='+998901234567', hire_date=date(2026, 1, 1))
        group = StudyGroup.objects.create(name='Fizika 1', course=course, teacher=teacher, start_date=date(2026, 1, 1))
        student = Student.objects.create(full_name='Sobir', phone='+998901111111')
        enrollment = Enrollment.objects.create(student=student, group=group, start_date=date(2026, 1, 1), monthly_price=Decimal('500000.00'))

        charge = generate_monthly_charge(enrollment_id=enrollment.id, billing_month=date(2026, 1, 1), user=user)

        def make_payment(amt, k):
            register_payment(student_id=student.id, amount=Decimal(amt), method=Payment.Method.CASH, user=user, idempotency_key=k)

        t1 = threading.Thread(target=make_payment, args=('200000.00', 'k1'))
        t2 = threading.Thread(target=make_payment, args=('300000.00', 'k2'))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        charge.refresh_from_db()
        self.assertEqual(charge.status, MonthlyCharge.Status.PAID)
        self.assertEqual(charge.allocated_amount, Decimal('500000.00'))
        self.assertEqual(student.total_debt, Decimal('0.00'))
