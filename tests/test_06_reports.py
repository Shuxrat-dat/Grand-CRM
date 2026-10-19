from decimal import Decimal
from datetime import date
from django.test import TestCase
from apps.accounts.models import User
from apps.students.models import Student
from apps.academics.models import Course, Teacher, StudyGroup, Enrollment
from apps.billing.models import MonthlyCharge, Payment, PaymentAllocation
from apps.payroll.models import SalaryRecord, SalaryPayment
from apps.finance.models import Expense
from apps.reporting.services import (
    get_cash_flow_report, get_accrual_profit_report, get_debtors_report
)


class ReportsTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner_reports', password='pwd', role=User.Role.OWNER)

        # Academics
        course = Course.objects.create(name='Kimyo', default_monthly_price=Decimal('500000.00'))
        teacher = Teacher.objects.create(full_name='Olim', phone='+998901112233', hire_date=date(2026, 1, 1))
        group = StudyGroup.objects.create(name='Kimyo 1', course=course, teacher=teacher, start_date=date(2026, 1, 1))

        # 2 Students
        self.student1 = Student.objects.create(full_name='Anvar', phone='+998901111111')
        self.student2 = Student.objects.create(full_name='Bekzod', phone='+998902222222')

        enr1 = Enrollment.objects.create(student=self.student1, group=group, start_date=date(2026, 1, 1), monthly_price=Decimal('500000.00'))
        enr2 = Enrollment.objects.create(student=self.student2, group=group, start_date=date(2026, 1, 1), monthly_price=Decimal('500000.00'))

        # Charges (Revenue Accrued = 1,000,000)
        c1 = MonthlyCharge.objects.create(student=self.student1, enrollment=enr1, billing_month=date(2026, 1, 1), amount=Decimal('500000.00'), due_date=date(2026, 1, 5))
        c2 = MonthlyCharge.objects.create(student=self.student2, enrollment=enr2, billing_month=date(2026, 1, 1), amount=Decimal('500000.00'), due_date=date(2026, 1, 5))

        from datetime import datetime, timezone as dt_timezone
        test_paid_at = datetime(2026, 1, 15, 10, 0, tzinfo=dt_timezone.utc)

        # Payments (Cash Inflows = 600,000)
        # Student 1 pays 500,000 in full
        p1 = Payment.objects.create(student=self.student1, amount=Decimal('500000.00'), method=Payment.Method.CASH, status=Payment.Status.COMPLETED, paid_at=test_paid_at)
        PaymentAllocation.objects.create(payment=p1, charge=c1, amount=Decimal('500000.00'))
        c1.refresh_status()

        # Student 2 pays 100,000 partially (400,000 debt remains)
        p2 = Payment.objects.create(student=self.student2, amount=Decimal('100000.00'), method=Payment.Method.CARD, status=Payment.Status.COMPLETED, paid_at=test_paid_at)
        PaymentAllocation.objects.create(payment=p2, charge=c2, amount=Decimal('100000.00'))
        c2.refresh_status()

        # Salary (Accrued = 3,000,000, Paid = 2,000,000)
        sal = SalaryRecord.objects.create(teacher=teacher, period_month=date(2026, 1, 1), amount=Decimal('3000000.00'), status=SalaryRecord.Status.APPROVED)
        SalaryPayment.objects.create(salary_record=sal, amount=Decimal('2000000.00'), method=SalaryPayment.Method.CARD, status=SalaryPayment.Status.COMPLETED, paid_at=test_paid_at)

        # Expense (300,000)
        Expense.objects.create(category='rent', amount=Decimal('300000.00'), occurred_at=date(2026, 1, 15), description='Bino ijarasi')

    def test_cash_flow_report_accuracy(self):
        """18a. Cash Flow report matches exact completed payments and disbursements."""
        cf = get_cash_flow_report(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))

        # Inflows: 500,000 + 100,000 = 600,000
        self.assertEqual(cf['inflows_total'], Decimal('600000.00'))
        # Salaries paid: 2,000,000
        self.assertEqual(cf['salaries_total'], Decimal('2000000.00'))
        # Operating expenses: 300,000
        self.assertEqual(cf['expenses_total'], Decimal('300000.00'))
        # Total Outflows: 2,300,000
        self.assertEqual(cf['outflows_total'], Decimal('2300000.00'))
        # Net Cash Flow: 600,000 - 2,300,000 = -1,700,000
        self.assertEqual(cf['net_cash_flow'], Decimal('-1700000.00'))

    def test_accrual_profit_report_accuracy(self):
        """18b. Accrual P&L strictly distinguishes accrued revenue from cash inflows."""
        pnl = get_accrual_profit_report(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))

        # Accrued Revenue: 500,000 + 500,000 = 1,000,000
        self.assertEqual(pnl['revenue_accrued'], Decimal('1000000.00'))
        # Accrued Salaries: 3,000,000
        self.assertEqual(pnl['salaries_accrued'], Decimal('3000000.00'))
        # Operating Expenses: 300,000
        self.assertEqual(pnl['expenses_accrued'], Decimal('300000.00'))
        # Total Costs: 3,300,000
        self.assertEqual(pnl['total_costs'], Decimal('3300000.00'))
        # Calculated Profit: 1,000,000 - 3,300,000 = -2,300,000
        self.assertEqual(pnl['calculated_profit'], Decimal('-2300000.00'))

    def test_debtors_report_accuracy(self):
        """18c. Debtors report matches exact outstanding balances."""
        debtors = get_debtors_report()
        # Only student2 has debt
        self.assertEqual(len(debtors), 1)
        self.assertEqual(debtors[0]['student'], self.student2)
        self.assertEqual(debtors[0]['total_debt'], Decimal('400000.00'))

    def test_reports_hub_accessible_by_owner_and_admin(self):
        """18d. Reports Hub endpoint returns 200 for both owner and admin."""
        from django.test import Client
        from django.urls import reverse

        client = Client()
        client.force_login(self.owner)
        res = client.get(reverse('reporting:reports_hub'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Hisobotlar Markazi")
        self.assertContains(res, "Pul oqimi")

        admin_user = User.objects.create_user(username='admin_reports', password='pwd', role=User.Role.ADMIN)
        client.force_login(admin_user)
        res = client.get(reverse('reporting:reports_hub'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Hisobotlar Markazi")
        # Admin should not see Cash Flow or Salaries on hub
        self.assertNotContains(res, "Pul oqimi (Cash Flow)")

    def test_excel_export_generation(self):
        """18e. Excel export downloads valid xlsx file."""
        from django.test import Client
        from django.urls import reverse

        client = Client()
        client.force_login(self.owner)
        res = client.get(reverse('reporting:export_report', args=['payments']) + '?format=excel')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

