from decimal import Decimal
from datetime import date, time, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import User
from apps.students.models import Student
from apps.academics.models import Course, Teacher, StudyGroup, GroupSchedule, Enrollment, EnrollmentPriceHistory
from apps.attendance.models import Lesson
from apps.billing.models import MonthlyCharge, Payment, PaymentAllocation
from apps.academics.services import (
    check_schedule_conflicts, create_schedule_slots,
    generate_lessons_from_schedules, update_enrollment_price,
    revert_enrollment_to_standard_price
)


class IndividualPricingAndSchedulesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin_aca', password='pwd', role=User.Role.ADMIN)
        self.course = Course.objects.create(
            name='Matematika',
            default_monthly_price=Decimal('450000.00'),
            duration_months=6
        )
        self.teacher1 = Teacher.objects.create(full_name='Anvar Ustoz', phone='+998901111111', hire_date=date(2026, 1, 1))
        self.teacher2 = Teacher.objects.create(full_name='Nodir Ustoz', phone='+998902222222', hire_date=date(2026, 1, 1))
        self.group1 = StudyGroup.objects.create(
            name='Math-01',
            course=self.course,
            teacher=self.teacher1,
            start_date=date(2026, 1, 1)
        )
        self.group2 = StudyGroup.objects.create(
            name='Math-02',
            course=self.course,
            teacher=self.teacher2,
            start_date=date(2026, 1, 1)
        )

        self.student_a = Student.objects.create(full_name='Akbar Aliyev', phone='+998903333333', joined_at=date(2026, 1, 1))
        self.student_b = Student.objects.create(full_name='Bekzod Boboyev', phone='+998904444444', joined_at=date(2026, 1, 1))

    # =========================================================================
    # TASK 5: INDIVIDUAL PRICING TESTS
    # =========================================================================

    def test_default_price_on_enrollment(self):
        """When student enrolls without specifying price, default course price is automatically snapshot."""
        enr = Enrollment.objects.create(
            student=self.student_a,
            group=self.group1,
            start_date=date(2026, 1, 1)
        )
        self.assertEqual(enr.monthly_price, Decimal('450000.00'))
        self.assertFalse(enr.is_custom_price)
        self.assertEqual(enr.discount_amount, Decimal('0.00'))

    def test_individual_price_update_and_history(self):
        """Updating a student's individual price does not change other students, records history and audit."""
        self.client.login(username='admin_aca', password='pwd')

        enr_a = Enrollment.objects.create(student=self.student_a, group=self.group1, start_date=date(2026, 1, 1))
        enr_b = Enrollment.objects.create(student=self.student_b, group=self.group1, start_date=date(2026, 1, 1))

        # Update Student B to 350,000 UZS with reason
        update_url = reverse('academics:enrollment_update_price', kwargs={'enrollment_id': enr_b.id})
        res = self.client.post(update_url, {
            'monthly_price': '350000.00',
            'reason_category': EnrollmentPriceHistory.ReasonCategory.DISCOUNT,
            'reason_details': 'Iqtidorli o‘quvchiga 100 ming so‘m chegirma',
            'update_current_unpaid_charge': True,
        })
        self.assertEqual(res.status_code, 302)

        enr_b.refresh_from_db()
        enr_a.refresh_from_db()

        # Student B has individual price
        self.assertEqual(enr_b.monthly_price, Decimal('350000.00'))
        self.assertTrue(enr_b.is_custom_price)
        self.assertEqual(enr_b.discount_amount, Decimal('100000.00'))
        self.assertIn('Chegirma', enr_b.custom_price_reason)

        # Student A is completely unaffected
        self.assertEqual(enr_a.monthly_price, Decimal('450000.00'))
        self.assertFalse(enr_a.is_custom_price)

        # Verify history entry created
        history = enr_b.price_histories.first()
        self.assertIsNotNone(history)
        self.assertEqual(history.old_price, Decimal('450000.00'))
        self.assertEqual(history.new_price, Decimal('350000.00'))
        self.assertEqual(history.changed_by, self.admin)

        # Revert Student B back to standard price
        revert_url = reverse('academics:enrollment_revert_price', kwargs={'enrollment_id': enr_b.id})
        rev_res = self.client.post(revert_url)
        self.assertEqual(rev_res.status_code, 302)

        enr_b.refresh_from_db()
        self.assertEqual(enr_b.monthly_price, Decimal('450000.00'))
        self.assertFalse(enr_b.is_custom_price)
        self.assertEqual(enr_b.price_histories.count(), 2)

    def test_price_change_preserves_paid_charges(self):
        """Changing tuition price does NOT recalculate or modify already paid past charges."""
        enr = Enrollment.objects.create(
            student=self.student_a,
            group=self.group1,
            start_date=date(2026, 1, 1),
            monthly_price=Decimal('450000.00')
        )
        # Paid past charge for January
        past_charge = MonthlyCharge.objects.create(
            student=self.student_a,
            enrollment=enr,
            billing_month=date(2026, 1, 1),
            amount=Decimal('450000.00'),
            due_date=date(2026, 1, 5),
            status=MonthlyCharge.Status.PAID
        )

        # Update price in February to 300,000 UZS
        update_enrollment_price(
            enrollment=enr,
            new_price=Decimal('300000.00'),
            reason="Rahbar qarori bilan",
            user=self.admin,
            update_unpaid_current=True
        )

        past_charge.refresh_from_db()
        self.assertEqual(past_charge.amount, Decimal('450000.00'))
        self.assertEqual(past_charge.status, MonthlyCharge.Status.PAID)

    # =========================================================================
    # TASK 6: SCHEDULES & LESSON GENERATION TESTS
    # =========================================================================

    def test_multi_day_slot_creation_and_conflict_detection(self):
        """Creates schedule slots across multiple weekdays, and blocks teacher/room/group conflicts."""
        self.client.login(username='admin_aca', password='pwd')

        # Create slots for Mon(1), Wed(3), Fri(5) 10:00 - 11:30 in Room 101 for Group 1 (Teacher 1)
        slots = create_schedule_slots(
            group=self.group1,
            weekdays=[1, 3, 5],
            start_time=time(10, 0),
            end_time=time(11, 30),
            room='101-xona',
            is_active=True,
            user=self.admin
        )
        self.assertEqual(len(slots), 3)

        # 1. Teacher conflict: Teacher 1 assigned to Group 2 on Monday 10:30 - 12:00
        self.group2.teacher = self.teacher1
        self.group2.save()
        conflicts = check_schedule_conflicts(
            group=self.group2,
            weekday=1,
            start_time=time(10, 30),
            end_time=time(12, 0),
            room='202-xona'
        )
        self.assertTrue(any("O'qituvchi" in c for c in conflicts))

        # 2. Room conflict: Room 101 occupied on Wednesday 11:00 - 12:30 by Group 2
        conflicts_room = check_schedule_conflicts(
            group=self.group2,
            weekday=3,
            start_time=time(11, 0),
            end_time=time(12, 30),
            room='101-xona'
        )
        self.assertTrue(any("101-xona" in c for c in conflicts_room))

        # 3. Group self-conflict: Group 1 already has lesson on Friday 10:00 - 11:30
        conflicts_group = check_schedule_conflicts(
            group=self.group1,
            weekday=5,
            start_time=time(10, 0),
            end_time=time(11, 30),
            room='303-xona'
        )
        self.assertTrue(any("guruhi" in c for c in conflicts_group))

    def test_slot_toggle_active_status(self):
        """Temporarily disables schedule slot without deleting it."""
        self.client.login(username='admin_aca', password='pwd')
        slot = GroupSchedule.objects.create(
            group=self.group1,
            weekday=2,
            start_time=time(14, 0),
            end_time=time(15, 30),
            is_active=True
        )

        toggle_url = reverse('academics:schedule_slot_toggle', kwargs={'slot_id': slot.id})
        res = self.client.post(toggle_url)
        self.assertEqual(res.status_code, 302)

        slot.refresh_from_db()
        self.assertFalse(slot.is_active)

    def test_lesson_generation_and_duplicate_prevention(self):
        """Generates lessons from active schedules for a date range without creating duplicates."""
        # Active schedule: Tuesday (weekday=2) and Thursday (weekday=4)
        GroupSchedule.objects.create(
            group=self.group1,
            weekday=2,
            start_time=time(9, 0),
            end_time=time(10, 30),
            room='Aud-1',
            is_active=True
        )
        GroupSchedule.objects.create(
            group=self.group1,
            weekday=4,
            start_time=time(9, 0),
            end_time=time(10, 30),
            room='Aud-1',
            is_active=True
        )

        # 2 weeks period: Jan 5, 2026 (Mon) to Jan 18, 2026 (Sun)
        # Tuesdays: Jan 6, Jan 13 (2)
        # Thursdays: Jan 8, Jan 15 (2)
        # Total = 4 lessons
        created_count, skipped_count = generate_lessons_from_schedules(
            group=self.group1,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 18),
            user=self.admin
        )
        self.assertEqual(created_count, 4)
        self.assertEqual(skipped_count, 0)
        self.assertEqual(Lesson.objects.filter(group=self.group1).count(), 4)

        # Run generator again for the exact same period -> should skip all 4 without creating duplicates
        created_again, skipped_again = generate_lessons_from_schedules(
            group=self.group1,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 18),
            user=self.admin
        )
        self.assertEqual(created_again, 0)
        self.assertEqual(skipped_again, 4)
        self.assertEqual(Lesson.objects.filter(group=self.group1).count(), 4)

    def test_calendar_views(self):
        """Calendar view loads successfully in month, week, and rooms modes."""
        self.client.login(username='admin_aca', password='pwd')
        cal_url = reverse('academics:schedule_calendar')

        # Month view
        res_m = self.client.get(f"{cal_url}?mode=month&year=2026&month=1")
        self.assertEqual(res_m.status_code, 200)
        self.assertContains(res_m, 'Darslar taqvimi')

        # Week view
        res_w = self.client.get(f"{cal_url}?mode=week&date=2026-01-05")
        self.assertEqual(res_w.status_code, 200)

        # Rooms view
        res_r = self.client.get(f"{cal_url}?mode=rooms&date=2026-01-06")
        self.assertEqual(res_r.status_code, 200)
