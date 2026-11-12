from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import GroupSchedule, StudyGroup, Enrollment, EnrollmentPriceHistory
from apps.attendance.models import Lesson
from apps.billing.models import MonthlyCharge
from apps.audit.services import log_audit


def check_schedule_conflicts(group, weekday, start_time, end_time, room=None, exclude_schedule_id=None):
    """
    Checks for conflicts on a given weekday and time interval:
    1. Teacher overlap across active groups
    2. Group self-overlap
    3. Room overlap across active groups
    Returns a list of conflict warning/error strings.
    """
    conflicts = []
    weekday = int(weekday)

    base_qs = GroupSchedule.objects.filter(
        is_active=True,
        weekday=weekday,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_schedule_id:
        base_qs = base_qs.exclude(id=exclude_schedule_id)

    # 1. Group conflict (same group cannot have two overlapping classes)
    group_conflict = base_qs.filter(group=group).first()
    if group_conflict:
        conflicts.append(
            f"'{group.name}' guruhi {group_conflict.get_weekday_display()} kuni {group_conflict.start_time.strftime('%H:%M')}-{group_conflict.end_time.strftime('%H:%M')} vaqtida boshqa darsga ega."
        )

    # 2. Teacher conflict
    if group.teacher_id:
        teacher_conflict = base_qs.filter(group__teacher_id=group.teacher_id).exclude(group=group).select_related('group').first()
        if teacher_conflict:
            conflicts.append(
                f"O'qituvchi {group.teacher.full_name} ushbu vaqtda '{teacher_conflict.group.name}' guruhida dars o'tadi ({teacher_conflict.start_time.strftime('%H:%M')}-{teacher_conflict.end_time.strftime('%H:%M')})."
            )

    # 3. Room conflict
    if room and room.strip():
        room_clean = room.strip()
        room_conflict = base_qs.filter(room__iexact=room_clean).exclude(group=group).select_related('group').first()
        if room_conflict:
            conflicts.append(
                f"'{room_clean}' auditoriyasi ushbu vaqtda '{room_conflict.group.name}' guruhi tomonidan band qilingan ({room_conflict.start_time.strftime('%H:%M')}-{room_conflict.end_time.strftime('%H:%M')})."
            )

    return conflicts


def create_schedule_slots(group, weekdays, start_time, end_time, room="", is_active=True, user=None):
    """
    Creates GroupSchedule slots for one or multiple weekdays at once.
    Checks conflicts before saving.
    """
    all_conflicts = []
    for w in weekdays:
        c = check_schedule_conflicts(group, w, start_time, end_time, room)
        all_conflicts.extend(c)

    if all_conflicts:
        raise ValidationError(all_conflicts)

    created_slots = []
    with transaction.atomic():
        for w in weekdays:
            slot = GroupSchedule.objects.create(
                group=group,
                weekday=int(w),
                start_time=start_time,
                end_time=end_time,
                room=room.strip(),
                is_active=is_active
            )
            created_slots.append(slot)

            log_audit(
                actor=user,
                action='CREATE',
                entity_type='GroupSchedule',
                entity_id=slot.id,
                changes_after={
                    'group': group.name,
                    'weekday': slot.get_weekday_display(),
                    'time': f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}",
                    'room': slot.room,
                    'is_active': slot.is_active,
                },
                reason=f"Yangi dars jadvali sloti yaratildi ({slot.get_weekday_display()})"
            )

    return created_slots


def generate_lessons_from_schedules(group=None, start_date=None, end_date=None, user=None):
    """
    Generates Lesson objects for a date range from active GroupSchedule slots.
    Guarantees zero duplicates.
    """
    if not start_date:
        start_date = timezone.now().date()
    if not end_date:
        end_date = start_date + timedelta(days=30)

    schedules_qs = GroupSchedule.objects.filter(is_active=True, group__is_active=True).select_related('group', 'group__course', 'group__teacher')
    if group:
        schedules_qs = schedules_qs.filter(group=group)

    # Index active schedules by (group_id, weekday)
    schedules_by_weekday = {}
    for sch in schedules_qs:
        key = (sch.group_id, sch.weekday)
        if key not in schedules_by_weekday:
            schedules_by_weekday[key] = []
        schedules_by_weekday[key].append(sch)

    # All target groups
    target_groups = {sch.group for sch in schedules_qs}

    created_count = 0
    skipped_count = 0

    curr = start_date
    with transaction.atomic():
        while curr <= end_date:
            weekday = curr.isoweekday() # 1=Mon .. 7=Sun

            for g in target_groups:
                slots = schedules_by_weekday.get((g.id, weekday), [])
                for slot in slots:
                    exists = Lesson.objects.filter(
                        group=g,
                        date=curr,
                        starts_at=slot.start_time
                    ).exists()

                    if exists:
                        skipped_count += 1
                    else:
                        Lesson.objects.create(
                            group=g,
                            date=curr,
                            starts_at=slot.start_time,
                            ends_at=slot.end_time,
                            room=slot.room,
                            topic=f"{g.course.name} darsi",
                            status=Lesson.Status.SCHEDULED
                        )
                        created_count += 1

            curr += timedelta(days=1)

        if created_count > 0:
            log_audit(
                actor=user,
                action='GENERATE_LESSONS',
                entity_type='Lesson',
                entity_id='BATCH',
                changes_after={
                    'group': group.name if group else 'ALL',
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'created_count': created_count,
                    'skipped_count': skipped_count,
                },
                reason=f"Jadval asosida {created_count} ta dars generatsiya qilindi ({start_date} dan {end_date} gacha)"
            )

    return created_count, skipped_count


def update_enrollment_price(enrollment: Enrollment, new_price: Decimal, reason: str, user=None, update_unpaid_current: bool = True):
    """
    Updates a student's individual tuition price for an enrollment.
    Saves price history, logs audit, and optionally updates current month's unpaid charge.
    NEVER touches already completed/paid past charges.
    """
    new_price = Decimal(str(new_price))
    old_price = enrollment.monthly_price

    with transaction.atomic():
        enrollment.monthly_price = new_price
        enrollment.custom_price_reason = reason.strip()
        enrollment.save(update_fields=['monthly_price', 'custom_price_reason', 'updated_at'])

        history = EnrollmentPriceHistory.objects.create(
            enrollment=enrollment,
            old_price=old_price,
            new_price=new_price,
            reason=reason.strip(),
            changed_by=user
        )

        log_audit(
            actor=user,
            action='UPDATE_PRICE',
            entity_type='Enrollment',
            entity_id=enrollment.id,
            changes_before={'monthly_price': str(old_price)},
            changes_after={
                'monthly_price': str(new_price),
                'reason': reason.strip(),
                'student': enrollment.student.full_name,
                'group': enrollment.group.name
            },
            reason=f"{enrollment.student.full_name} uchun individual narx {new_price} so'mga o'zgartirildi ({reason})"
        )

        # Update current month's unpaid or partial charge if requested
        if update_unpaid_current:
            today = timezone.now().date()
            current_month_first = date(today.year, today.month, 1)

            current_charge = MonthlyCharge.objects.filter(
                enrollment=enrollment,
                billing_month=current_month_first,
                status__in=[MonthlyCharge.Status.UNPAID, MonthlyCharge.Status.PARTIAL]
            ).first()

            if current_charge:
                current_charge.amount = new_price
                current_charge.save(update_fields=['amount'])
                current_charge.refresh_status()

    return history


def revert_enrollment_to_standard_price(enrollment: Enrollment, user=None, update_unpaid_current: bool = True):
    """
    Reverts enrollment individual price back to group's course default price.
    """
    standard_price = enrollment.group.course.default_monthly_price
    reason = "Standart kurs narxiga qaytarildi"
    return update_enrollment_price(
        enrollment=enrollment,
        new_price=standard_price,
        reason=reason,
        user=user,
        update_unpaid_current=update_unpaid_current
    )
