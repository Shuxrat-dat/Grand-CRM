from datetime import date, time
from django.test import TestCase, Client
from django.db import IntegrityError
from django.urls import reverse
from apps.accounts.models import User
from apps.students.models import Student
from apps.academics.models import Course, Teacher, StudyGroup, Enrollment
from apps.attendance.models import Lesson, AttendanceRecord
from apps.audit.models import AuditLog


class AttendanceTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin_att', password='pwd', role=User.Role.ADMIN)
        self.course = Course.objects.create(name='Biologiya', default_monthly_price=400000)
        self.teacher = Teacher.objects.create(full_name='Zuhra', phone='+998901234567', hire_date=date(2026, 1, 1))
        self.group = StudyGroup.objects.create(name='Bio 1', course=self.course, teacher=self.teacher, start_date=date(2026, 1, 1))
        self.student = Student.objects.create(full_name='Madina', phone='+998901112233', joined_at=date(2026, 1, 1))
        self.enrollment = Enrollment.objects.create(student=self.student, group=self.group, start_date=date(2026, 1, 1), monthly_price=400000)

        self.lesson = Lesson.objects.create(
            group=self.group,
            date=date(2026, 1, 15),
            starts_at=time(10, 0),
            ends_at=time(11, 30)
        )

    def test_duplicate_attendance_prohibited(self):
        """14. Database constraint prevents duplicate attendance records for same student and lesson."""
        AttendanceRecord.objects.create(
            lesson=self.lesson,
            student=self.student,
            status=AttendanceRecord.Status.PRESENT,
            marked_by=self.admin
        )

        with self.assertRaises(IntegrityError):
            AttendanceRecord.objects.create(
                lesson=self.lesson,
                student=self.student,
                status=AttendanceRecord.Status.ABSENT,
                marked_by=self.admin
            )

    def test_attendance_mark_correction_preserves_audit_trail(self):
        """15. Correcting an attendance mark preserves full audit trail in AuditLog."""
        self.client.login(username='admin_att', password='pwd')

        # First mark: present
        url = reverse('attendance:lesson_attendance', kwargs={'lesson_id': self.lesson.id})
        res1 = self.client.post(url, {
            f'status_{self.student.id}': 'present',
            f'note_{self.student.id}': 'Darsda faol'
        })
        self.assertEqual(res1.status_code, 302)

        att = AttendanceRecord.objects.get(lesson=self.lesson, student=self.student)
        self.assertEqual(att.status, AttendanceRecord.Status.PRESENT)

        # Correction: absent with reason
        res2 = self.client.post(url, {
            f'status_{self.student.id}': 'excused',
            f'note_{self.student.id}': 'Kasal bo\'lib qolgan ekan'
        })
        self.assertEqual(res2.status_code, 302)

        att.refresh_from_db()
        self.assertEqual(att.status, AttendanceRecord.Status.EXCUSED)

        # Verify audit log captures old and new status
        update_log = AuditLog.objects.filter(
            entity_type='AttendanceRecord',
            entity_id=str(att.id),
            action='UPDATE'
        ).first()

        self.assertIsNotNone(update_log)
        self.assertEqual(update_log.changes_before['status'], 'present')
        self.assertEqual(update_log.changes_after['status'], 'excused')

    def test_absent_requires_reason_and_comment(self):
        """Marking a student as absent strictly requires reason and comment."""
        self.client.login(username='admin_att', password='pwd')
        url = reverse('attendance:lesson_attendance', kwargs={'lesson_id': self.lesson.id})

        # Try posting absent without reason and without note
        res_fail = self.client.post(url, {
            f'status_{self.student.id}': 'absent',
            f'reason_{self.student.id}': '',
            f'note_{self.student.id}': '',
        })
        self.assertEqual(res_fail.status_code, 200) # Re-rendered with error messages
        self.assertFalse(AttendanceRecord.objects.filter(student=self.student, status='absent').exists())

        # Try posting absent with reason but empty note
        res_fail2 = self.client.post(url, {
            f'status_{self.student.id}': 'absent',
            f'reason_{self.student.id}': 'bemor',
            f'note_{self.student.id}': '',
        })
        self.assertEqual(res_fail2.status_code, 200)
        self.assertFalse(AttendanceRecord.objects.filter(student=self.student, status='absent').exists())

    def test_absent_saves_reason_comment_date_and_admin(self):
        """Saving absent with valid reason and comment stores reason, notes, lesson date and marked_by."""
        self.client.login(username='admin_att', password='pwd')
        url = reverse('attendance:lesson_attendance', kwargs={'lesson_id': self.lesson.id})

        res = self.client.post(url, {
            f'status_{self.student.id}': 'absent',
            f'reason_{self.student.id}': 'bemor',
            f'note_{self.student.id}': 'Shamollagan, 2 kunga javob so‘ragan',
        })
        self.assertEqual(res.status_code, 302)

        att = AttendanceRecord.objects.get(lesson=self.lesson, student=self.student)
        self.assertEqual(att.status, AttendanceRecord.Status.ABSENT)
        self.assertEqual(att.absence_reason, AttendanceRecord.AbsenceReason.BEMOR)
        self.assertEqual(att.notes, 'Shamollagan, 2 kunga javob so‘ragan')
        self.assertEqual(att.marked_by, self.admin)
        self.assertEqual(att.lesson.date, date(2026, 1, 15))

        # Check absence history view
        history_url = reverse('attendance:student_absences', kwargs={'student_id': self.student.id})
        h_res = self.client.get(history_url)
        self.assertEqual(h_res.status_code, 200)
        self.assertContains(h_res, 'Shamollagan, 2 kunga javob so‘ragan')
        self.assertContains(h_res, 'Bemor')
        self.assertContains(h_res, self.admin.username)
