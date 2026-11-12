from datetime import date
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User
from apps.academics.models import Course, Teacher, StudyGroup, Enrollment
from apps.students.models import Student
from apps.audit.models import AuditLog
from apps.leads.models import Lead


class LeadsModuleTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin_lead', password='pwd', role=User.Role.ADMIN)
        self.course = Course.objects.create(name='Ingliz tili (IELTS)', default_monthly_price=Decimal('500000.00'))
        self.teacher = Teacher.objects.create(full_name='Aziz Teacher', phone='+998901112233', hire_date=date(2026, 1, 1))
        self.group = StudyGroup.objects.create(
            name='IELTS-01',
            course=self.course,
            teacher=self.teacher,
            start_date=date(2026, 1, 1)
        )

    def test_lead_creation_and_listing(self):
        """Lead is created with all fields and listed on leads list view with statistics."""
        self.client.login(username='admin_lead', password='pwd')

        # Create lead via form
        create_url = reverse('leads:lead_create')
        res = self.client.post(create_url, {
            'full_name': 'Ali Valiyev',
            'phone': '+998901234567',
            'course': self.course.id,
            'source': Lead.Source.TELEGRAM,
            'status': Lead.Status.YANGI,
            'notes': 'Telegram bot orqali murojaat qildi',
        })
        self.assertEqual(res.status_code, 302)

        lead = Lead.objects.get(phone='+998901234567')
        self.assertEqual(lead.full_name, 'Ali Valiyev')
        self.assertEqual(lead.source, Lead.Source.TELEGRAM)
        self.assertEqual(lead.status, Lead.Status.YANGI)
        self.assertFalse(lead.is_converted)

        # Verify audit log
        audit = AuditLog.objects.filter(entity_type='Lead', entity_id=str(lead.id), action='CREATE').first()
        self.assertIsNotNone(audit)

        # Check leads list page & statistics
        list_url = reverse('leads:leads_list')
        list_res = self.client.get(list_url)
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, 'Ali Valiyev')
        self.assertContains(list_res, '+998901234567')
        self.assertContains(list_res, 'Ingliz tili (IELTS)')
        self.assertEqual(list_res.context['total_leads_count'], 1)
        self.assertEqual(list_res.context['new_leads_count'], 1)
        self.assertEqual(list_res.context['converted_leads_count'], 0)
        self.assertEqual(list_res.context['conversion_rate'], 0.0)

    def test_lead_search_and_filtering(self):
        """Search by query and filter by status and course work accurately."""
        self.client.login(username='admin_lead', password='pwd')

        lead1 = Lead.objects.create(
            full_name='Rustam Karimov',
            phone='+998911111111',
            course=self.course,
            source=Lead.Source.INSTAGRAM,
            status=Lead.Status.YANGI
        )
        lead2 = Lead.objects.create(
            full_name='Dilnoza Rahimova',
            phone='+998922222222',
            source=Lead.Source.PHONE,
            status=Lead.Status.BOGLANILDI
        )

        list_url = reverse('leads:leads_list')

        # Search by name
        res_search = self.client.get(f"{list_url}?q=Rustam")
        self.assertContains(res_search, 'Rustam Karimov')
        self.assertNotContains(res_search, 'Dilnoza Rahimova')

        # Filter by status
        res_filter = self.client.get(f"{list_url}?status=boglanildi")
        self.assertContains(res_filter, 'Dilnoza Rahimova')
        self.assertNotContains(res_filter, 'Rustam Karimov')

    def test_lead_conversion_to_student_and_duplicate_prevention(self):
        """
        Main Feature:
        When admin converts lead, a Student is created in O'quvchilar, enrolled into selected group,
        lead status changes to CONVERTED, row becomes light-green, student link appears,
        and duplicate conversion is strictly prohibited.
        """
        self.client.login(username='admin_lead', password='pwd')

        lead = Lead.objects.create(
            full_name='Jasur Bekmurodov',
            phone='+998933334455',
            course=self.course,
            source=Lead.Source.PERSONAL,
            status=Lead.Status.SINOV_DARSI,
            notes='Kechki guruhga qiziqmoqda'
        )

        convert_url = reverse('leads:lead_convert', kwargs={'lead_id': lead.id})

        # GET convert page
        get_res = self.client.get(convert_url)
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, 'Jasur Bekmurodov')

        # POST convert form
        post_res = self.client.post(convert_url, {
            'group': self.group.id,
            'start_date': date(2026, 1, 10),
            'monthly_price': Decimal('480000.00'),
            'parent_phone': '+998939998877',
        })
        # Successfully redirects to student detail page
        self.assertEqual(post_res.status_code, 302)

        # Verify Student created in O'quvchilar
        student = Student.objects.get(phone='+998933334455')
        self.assertEqual(student.full_name, 'Jasur Bekmurodov')
        self.assertEqual(student.parent_phone, '+998939998877')
        self.assertEqual(student.joined_at, date(2026, 1, 10))
        self.assertEqual(student.status, Student.Status.ACTIVE)
        self.assertIn('Liddan aylantirildi', student.notes)

        # Verify Enrollment created in selected group
        enrollment = Enrollment.objects.get(student=student, group=self.group)
        self.assertEqual(enrollment.monthly_price, Decimal('480000.00'))
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)

        # Verify Lead record updated
        lead.refresh_from_db()
        self.assertTrue(lead.is_converted)
        self.assertEqual(lead.status, Lead.Status.CONVERTED)
        self.assertEqual(lead.converted_student, student)
        self.assertEqual(lead.converted_by, self.admin)
        self.assertIsNotNone(lead.converted_at)

        # Verify Lead AuditLog
        audit = AuditLog.objects.filter(entity_type='Lead', entity_id=str(lead.id), action='CONVERT_LEAD').first()
        self.assertIsNotNone(audit)

        # Check Leads list page: row has table-success, status is converted, link to student exists
        list_res = self.client.get(reverse('leads:leads_list'))
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, 'table-success')
        self.assertContains(list_res, 'O‘quvchiga aylantirildi')
        self.assertContains(list_res, reverse('students:student_detail', kwargs={'student_id': student.id}))
        self.assertEqual(list_res.context['converted_leads_count'], 1)
        self.assertEqual(list_res.context['conversion_rate'], 100.0)

        # Verify Duplicate conversion prevention:
        # Attempting to convert again redirects and refuses to create a duplicate student
        initial_student_count = Student.objects.count()
        dup_res = self.client.post(convert_url, {
            'group': self.group.id,
            'start_date': date(2026, 1, 12),
        })
        self.assertEqual(dup_res.status_code, 302)
        self.assertEqual(Student.objects.count(), initial_student_count)

    def test_lead_edit_and_delete(self):
        """Lead can be edited and deleted with audit logging."""
        self.client.login(username='admin_lead', password='pwd')

        lead = Lead.objects.create(
            full_name='Nodir Ergashev',
            phone='+998945556677',
            status=Lead.Status.YANGI
        )

        edit_url = reverse('leads:lead_edit', kwargs={'lead_id': lead.id})
        edit_res = self.client.post(edit_url, {
            'full_name': 'Nodir Ergashev (Tahrirlandi)',
            'phone': '+998945556677',
            'source': Lead.Source.RECOMMENDATION,
            'status': Lead.Status.KUTILMOQDA,
            'notes': 'Dushanba kuni keladi',
        })
        self.assertEqual(edit_res.status_code, 302)
        lead.refresh_from_db()
        self.assertEqual(lead.full_name, 'Nodir Ergashev (Tahrirlandi)')
        self.assertEqual(lead.status, Lead.Status.KUTILMOQDA)

        # Delete lead
        del_url = reverse('leads:lead_delete', kwargs={'lead_id': lead.id})
        del_res = self.client.post(del_url)
        self.assertEqual(del_res.status_code, 302)
        self.assertFalse(Lead.objects.filter(id=lead.id).exists())
