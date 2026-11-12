from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import User
from apps.students.models import Student
from apps.academics.models import Course, Teacher, StudyGroup, Enrollment
from apps.accounts.widgets import DynamicSearchSelect
from apps.academics.forms import EnrollmentForm, StudyGroupForm
from apps.billing.forms import PaymentForm


class UniversalSearchAndPaymentStatusTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner_user', password='pwd', role=User.Role.OWNER)
        self.admin = User.objects.create_user(username='admin_user', password='pwd', role=User.Role.ADMIN)

        self.course = Course.objects.create(
            name='Ingliz tili IELTS',
            default_monthly_price=Decimal('500000.00'),
            duration_months=3
        )
        self.teacher1 = Teacher.objects.create(
            full_name='Ali Valiyev',
            phone='+998901112233',
            specialization='General English'
        )
        self.teacher2 = Teacher.objects.create(
            full_name='Vali Aliyev',
            phone='+998904445566',
            specialization='IELTS Expert'
        )

        self.group = StudyGroup.objects.create(
            name='IELTS 10:00',
            course=self.course,
            teacher=self.teacher1,
            capacity=15,
            start_date=date(2026, 1, 1)
        )

        self.student1 = Student.objects.create(
            full_name='Rustam Karimov',
            phone='+998901234567',
            parent_phone='+998907654321',
            joined_at=date(2026, 1, 1)
        )
        self.student2 = Student.objects.create(
            full_name='Karim Rustamov',
            phone='+998909876543',
            joined_at=date(2026, 1, 2)
        )

        self.enrollment = Enrollment.objects.create(
            student=self.student1,
            group=self.group,
            start_date=date(2026, 1, 1),
            monthly_price=Decimal('500000.00'),
            payment_status=Enrollment.PaymentStatus.UNPAID
        )

    # --- TASK 1: DYNAMIC SEARCH TESTS ---

    def test_search_students_api_min_chars(self):
        """Dynamic search API returns empty when less than 3 characters."""
        self.client.force_login(self.admin)
        url = reverse('api_search_students')

        res = self.client.get(url, {'q': 'Ru'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['results'], [])

    def test_search_students_api_finds_by_name_and_surname(self):
        """Dynamic search API finds students by first name and last name."""
        self.client.force_login(self.admin)
        url = reverse('api_search_students')

        # Search by first name
        res = self.client.get(url, {'q': 'Rustam'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data['results']), 2)

        # Search by last name
        res = self.client.get(url, {'q': 'Karimov'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['id'], self.student1.id)
        self.assertEqual(data['results'][0]['full_name'], 'Rustam Karimov')

    def test_search_teachers_api(self):
        """Dynamic search API finds teachers by first and last name after 3+ chars."""
        self.client.force_login(self.admin)
        url = reverse('api_search_teachers')

        # Min chars check
        res = self.client.get(url, {'q': 'Al'})
        self.assertEqual(res.json()['results'], [])

        # Search query
        res = self.client.get(url, {'q': 'Valiyev'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['id'], self.teacher1.id)
        self.assertEqual(data['results'][0]['full_name'], 'Ali Valiyev')

    def test_universal_search_api(self):
        """Universal search returns both students and teachers matching query."""
        self.client.force_login(self.admin)
        url = reverse('api_search_universal')

        # Query matching student1 ("Rustam Karimov")
        res = self.client.get(url, {'q': 'Karim'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(len(data['students']) >= 1)

        # Query matching teachers ("Ali")
        res = self.client.get(url, {'q': 'Ali'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(len(data['teachers']) >= 2)

    def test_dynamic_search_widget_efficiency(self):
        """Widget renders only blank and preselected option, not all records."""
        widget = DynamicSearchSelect(
            search_url='/api/search/students/',
            model=Student,
            placeholder="O'quvchini qidirish"
        )

        # Rendering with no value
        html_empty = widget.render('student', None)
        self.assertIn('dynamic-search-select', html_empty)
        self.assertIn('data-search-url="/api/search/students/"', html_empty)
        self.assertIn('data-min-chars="3"', html_empty)
        self.assertNotIn('Rustam Karimov', html_empty)

        # Rendering with selected value
        html_selected = widget.render('student', self.student1.id)
        self.assertIn(f'value="{self.student1.id}"', html_selected)
        self.assertIn('Rustam Karimov', html_selected)
        self.assertNotIn('Karim Rustamov', html_selected)

    def test_forms_with_dynamic_search(self):
        """Forms validate and save properly with dynamic select widget."""
        # EnrollmentForm
        form = EnrollmentForm(data={
            'student': self.student2.id,
            'group': self.group.id,
            'start_date': '2026-02-01',
            'monthly_price': '500000.00',
            'payment_status': 'paid'
        })
        self.assertTrue(form.is_valid(), form.errors)
        new_enr = form.save()
        self.assertEqual(new_enr.student, self.student2)
        self.assertEqual(new_enr.payment_status, 'paid')

        # StudyGroupForm
        group_form = StudyGroupForm(data={
            'name': 'New Group',
            'course': self.course.id,
            'teacher': self.teacher2.id,
            'capacity': 10,
            'start_date': '2026-02-01',
            'is_active': True
        })
        self.assertTrue(group_form.is_valid(), group_form.errors)
        new_grp = group_form.save()
        self.assertEqual(new_grp.teacher, self.teacher2)

    # --- TASK 2: GROUP PAYMENT STATUS TESTS ---

    def test_enrollment_payment_status_default(self):
        """New enrollments default to unpaid."""
        enr = Enrollment.objects.create(
            student=self.student2,
            group=self.group,
            start_date=date(2026, 1, 5),
            monthly_price=Decimal('500000.00')
        )
        self.assertEqual(enr.payment_status, Enrollment.PaymentStatus.UNPAID)
        self.assertEqual(enr.get_payment_status_display(), 'To‘lanmadi')

    def test_enrollment_update_payment_status_view(self):
        """Updating payment status via view persists and can toggle between paid and unpaid."""
        self.client.force_login(self.admin)
        url = reverse('academics:enrollment_update_payment_status', args=[self.enrollment.id])

        # POST change to paid
        res = self.client.post(url, {'payment_status': 'paid'})
        self.assertRedirects(res, reverse('academics:group_detail', args=[self.group.id]))

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.payment_status, Enrollment.PaymentStatus.PAID)
        self.assertEqual(self.enrollment.get_payment_status_display(), 'To‘landi')

        # AJAX POST change back to unpaid
        ajax_res = self.client.post(
            url,
            {'payment_status': 'unpaid'},
            headers={'x-requested-with': 'XMLHttpRequest'}
        )
        self.assertEqual(ajax_res.status_code, 200)
        data = ajax_res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['payment_status'], 'unpaid')
        self.assertFalse(data['is_paid'])

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.payment_status, Enrollment.PaymentStatus.UNPAID)

    def test_group_detail_displays_payment_status_column(self):
        """Group detail page contains To'lov holati column instead of Qo'shilgan sana."""
        self.client.force_login(self.admin)
        url = reverse('academics:group_detail', args=[self.group.id])
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        # Verify To'lov holati header is present
        self.assertIn('To‘lov holati', content)
        # Verify Qo'shilgan sana header is NOT in table headers
        self.assertNotIn('<th>Qo‘shilgan sana</th>', content)

        # Verify status badges/dropdown buttons
        self.assertIn('payment-status-btn', content)
        self.assertIn('To‘lanmadi', content)

        # Change status to paid and check that green To'landi badge is shown
        self.enrollment.payment_status = Enrollment.PaymentStatus.PAID
        self.enrollment.save()

        res_paid = self.client.get(url)
        content_paid = res_paid.content.decode('utf-8')
        self.assertIn('btn-success', content_paid)
        self.assertIn('To‘landi', content_paid)

        # Verify start_date is still preserved in DB
        self.assertEqual(self.enrollment.start_date, date(2026, 1, 1))
