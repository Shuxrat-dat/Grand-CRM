from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class Course(models.Model):
    name = models.CharField(max_length=200, verbose_name="Kurs nomi")
    description = models.TextField(blank=True, verbose_name="Tavsif")
    default_monthly_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Standart oylik narx"
    )
    duration_months = models.PositiveIntegerField(
        default=3,
        verbose_name="Davomiyligi (oy)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Kurs"
        verbose_name_plural = "Kurslar"
        ordering = ['name']

    def __str__(self):
        return self.name


class Teacher(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Faol'
        INACTIVE = 'inactive', 'Nofaol'

    full_name = models.CharField(max_length=255, verbose_name="O'qituvchi F.I.SH.")
    phone = models.CharField(max_length=30, verbose_name="Telefon raqami")
    specialization = models.CharField(max_length=255, blank=True, verbose_name="Mutaxassisligi")
    hire_date = models.DateField(default=timezone.now, verbose_name="Ishga kirgan sana")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Holati"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "O'qituvchi"
        verbose_name_plural = "O'qituvchilar"
        ordering = ['full_name']

    def __str__(self):
        return self.full_name

    def get_salary_rate_for_date(self, target_date=None):
        """
        Returns the active TeacherSalaryRate for a given date.
        If target_date is None, current date is used.
        Past rates are preserved and future rates only apply from valid_from.
        """
        if target_date is None:
            target_date = timezone.now().date()
        
        rates = self.salary_rates.filter(
            valid_from__lte=target_date
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=target_date)
        ).order_by('-valid_from')
        return rates.first()


class TeacherSalaryRate(models.Model):
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name='salary_rates',
        verbose_name="O'qituvchi"
    )
    monthly_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Oylik maosh miqdori"
    )
    valid_from = models.DateField(verbose_name="Amal qilish boshlanishi")
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="Amal qilish tugashi (ixtiyoriy)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "O'qituvchi oylik stavkasi"
        verbose_name_plural = "O'qituvchilar stavkalari"
        ordering = ['-valid_from']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F('valid_from')),
                name='salary_rate_valid_to_gte_valid_from'
            )
        ]

    def clean(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValidationError("Tugash sanasi boshlanish sanasidan oldin bo'lishi mumkin emas.")

    def __str__(self):
        to_str = self.valid_to.strftime('%Y-%m-%d') if self.valid_to else "hozirgacha"
        return f"{self.teacher.full_name} - {self.monthly_amount} so'm ({self.valid_from} dan {to_str})"


class StudyGroup(models.Model):
    name = models.CharField(max_length=150, verbose_name="Guruh nomi")
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name='groups',
        verbose_name="Kurs"
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name='groups',
        verbose_name="O'qituvchi"
    )
    capacity = models.PositiveIntegerField(default=15, verbose_name="Maksimal sig'im")
    start_date = models.DateField(verbose_name="Boshlanish sanasi")
    end_date = models.DateField(null=True, blank=True, verbose_name="Tugash sanasi")
    is_active = models.BooleanField(default=True, verbose_name="Faol guruh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.course.name})"

    @property
    def active_students_count(self):
        return self.enrollments.filter(status='active').count()


class GroupSchedule(models.Model):
    class Weekday(models.IntegerChoices):
        DUSHANBA = 1, 'Dushanba'
        SESHANBA = 2, 'Seshanba'
        CHORSHANBA = 3, 'Chorshanba'
        PAYSHANBA = 4, 'Payshanba'
        JUMA = 5, 'Juma'
        SHANBA = 6, 'Shanba'
        YAKSHANBA = 7, 'Yakshanba'

    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name="Guruh"
    )
    weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices,
        verbose_name="Hafta kuni"
    )
    start_time = models.TimeField(verbose_name="Boshlanish vaqti")
    end_time = models.TimeField(verbose_name="Tugash vaqti")
    room = models.CharField(max_length=100, blank=True, verbose_name="Xona / Auditoriya")

    class Meta:
        verbose_name = "Dars jadvali"
        verbose_name_plural = "Dars jadvallari"
        ordering = ['weekday', 'start_time']

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError("Dars tugash vaqti boshlanish vaqtidan kechroq bo'lishi shart.")

    def __str__(self):
        return f"{self.group.name}: {self.get_weekday_display()} {self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Faol'
        TRANSFERRED = 'transferred', "Ko'chirilgan"
        COMPLETED = 'completed', 'Yakunlangan'
        DROPPED = 'dropped', "To'xtatilgan"

    student = models.ForeignKey(
        'students.Student',
        on_delete=models.PROTECT,
        related_name='enrollments',
        verbose_name="O'quvchi"
    )
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.PROTECT,
        related_name='enrollments',
        verbose_name="Guruh"
    )
    start_date = models.DateField(verbose_name="A'zolik boshlanish sanasi")
    end_date = models.DateField(null=True, blank=True, verbose_name="Tugash sanasi")
    monthly_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Kelishilgan oylik narx"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="A'zolik holati"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Guruhga a'zolik"
        verbose_name_plural = "Guruh a'zoliklari"
        ordering = ['-start_date']

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("A'zolik tugash sanasi boshlanish sanasidan oldin bo'lishi mumkin emas.")

    def save(self, *args, **kwargs):
        # Default to group course default price if not set
        if not self.monthly_price and self.group and self.group.course:
            self.monthly_price = self.group.course.default_monthly_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.full_name} -> {self.group.name} ({self.monthly_price} so'm)"
