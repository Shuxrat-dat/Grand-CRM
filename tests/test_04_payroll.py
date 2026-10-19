from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.accounts.models import User
from apps.academics.models import Teacher, TeacherSalaryRate
from apps.payroll.models import SalaryRecord, SalaryPayment
from apps.payroll.services import (
    generate_monthly_salary, approve_salary, register_salary_payment
)


class PayrollTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner_payroll', password='pwd', role=User.Role.OWNER)
        self.teacher = Teacher.objects.create(
            full_name='Nodirbek Qodirov',
            phone='+998905554433',
            hire_date=date(2026, 1, 1)
        )
        # Rate from Jan 1: 4,000,000
        self.rate_jan = TeacherSalaryRate.objects.create(
            teacher=self.teacher,
            monthly_amount=Decimal('4000000.00'),
            valid_from=date(2026, 1, 1)
        )

    def test_salary_accrual_from_active_rate(self):
        """11. Salary accrual calculation matches active rate on that period."""
        salary = generate_monthly_salary(
            teacher_id=self.teacher.id,
            period_month=date(2026, 1, 1),
            user=self.owner
        )
        self.assertEqual(salary.amount, Decimal('4000000.00'))
        self.assertEqual(salary.status, SalaryRecord.Status.PENDING)

    def test_future_rate_change_does_not_affect_old_accruals(self):
        """12. Changing future rate does not alter old historical accruals."""
        salary_jan = generate_monthly_salary(
            teacher_id=self.teacher.id,
            period_month=date(2026, 1, 1),
            user=self.owner
        )
        self.assertEqual(salary_jan.amount, Decimal('4000000.00'))

        # In March, rate increases to 5,000,000
        self.rate_jan.valid_to = date(2026, 2, 28)
        self.rate_jan.save()
        rate_mar = TeacherSalaryRate.objects.create(
            teacher=self.teacher,
            monthly_amount=Decimal('5000000.00'),
            valid_from=date(2026, 3, 1)
        )

        salary_mar = generate_monthly_salary(
            teacher_id=self.teacher.id,
            period_month=date(2026, 3, 1),
            user=self.owner
        )

        # January historical record MUST remain 4,000,000
        salary_jan.refresh_from_db()
        self.assertEqual(salary_jan.amount, Decimal('4000000.00'))
        # March record is 5,000,000
        self.assertEqual(salary_mar.amount, Decimal('5000000.00'))

    def test_partial_salary_payment_and_overpay_protection(self):
        """13. Partial salary payout and prevention of overpayment beyond remaining balance."""
        salary = generate_monthly_salary(
            teacher_id=self.teacher.id,
            period_month=date(2026, 1, 1),
            user=self.owner
        )
        approve_salary(salary_id=salary.id, user=self.owner)

        # Partial payment: 2,500,000
        pay1 = register_salary_payment(
            salary_id=salary.id,
            amount=Decimal('2500000.00'),
            method=SalaryPayment.Method.CARD,
            user=self.owner
        )

        salary.refresh_from_db()
        self.assertEqual(salary.status, SalaryRecord.Status.PARTIAL)
        self.assertEqual(salary.total_paid, Decimal('2500000.00'))
        self.assertEqual(salary.remaining_balance, Decimal('1500000.00'))

        # Attempt to overpay 2,000,000 when remaining is 1,500,000 without permission
        with self.assertRaises(ValidationError):
            register_salary_payment(
                salary_id=salary.id,
                amount=Decimal('2000000.00'),
                method=SalaryPayment.Method.CASH,
                user=self.owner,
                allow_overpay=False
            )

        # Pay remaining exact 1,500,000
        pay2 = register_salary_payment(
            salary_id=salary.id,
            amount=Decimal('1500000.00'),
            method=SalaryPayment.Method.CASH,
            user=self.owner
        )

        salary.refresh_from_db()
        self.assertEqual(salary.status, SalaryRecord.Status.PAID)
        self.assertEqual(salary.remaining_balance, Decimal('0.00'))
