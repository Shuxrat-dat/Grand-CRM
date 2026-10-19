from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class Lesson(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Rejalashtirilgan'
        COMPLETED = 'completed', "O'tilgan"
        CANCELLED = 'cancelled', 'Bekor qilingan'

    group = models.ForeignKey(
        'academics.StudyGroup',
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name="Guruh"
    )
    date = models.DateField(default=timezone.now, verbose_name="Dars sanasi")
    starts_at = models.TimeField(verbose_name="Boshlanish vaqti")
    ends_at = models.TimeField(verbose_name="Tugash vaqti")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        verbose_name="Dars holati"
    )
    topic = models.CharField(max_length=255, blank=True, verbose_name="Dars mavzusi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "Dars"
        verbose_name_plural = "Darslar"
        ordering = ['-date', '-starts_at']
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'date', 'starts_at'],
                name='unique_lesson_per_group_date_time'
            )
        ]

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError("Dars tugash vaqti boshlanish vaqtidan kechroq bo'lishi kerak.")

    def __str__(self):
        return f"{self.group.name} | {self.date} {self.starts_at.strftime('%H:%M')}"


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Qatnashdi'
        ABSENT = 'absent', 'Qatnashmadi'
        LATE = 'late', 'Kechikdi'
        EXCUSED = 'excused', 'Sababli'

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name="Dars"
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.PROTECT,
        related_name='attendances',
        verbose_name="O'quvchi"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PRESENT,
        verbose_name="Davomat holati"
    )
    notes = models.CharField(max_length=255, blank=True, verbose_name="Qayd / Izoh")
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marked_attendances',
        verbose_name="Belgilagan xodim"
    )
    marked_at = models.DateTimeField(auto_now_add=True, verbose_name="Belgilangan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        verbose_name = "Davomat yozuvi"
        verbose_name_plural = "Davomat yozuvlari"
        constraints = [
            models.UniqueConstraint(
                fields=['lesson', 'student'],
                name='unique_attendance_per_lesson_student'
            )
        ]

    def clean(self):
        # Verify student was enrolled in the lesson's group on the lesson's date
        enrollment_exists = self.student.enrollments.filter(
            group=self.lesson.group,
            start_date__lte=self.lesson.date
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=self.lesson.date)
        ).exists()

        if not enrollment_exists:
            raise ValidationError(
                f"{self.student.full_name} ushbu guruhga {self.lesson.date} sanasida a'zo bo'lmagan."
            )

    def __str__(self):
        return f"{self.student.full_name} - {self.get_status_display()} ({self.lesson})"
