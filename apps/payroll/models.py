from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum


class SalaryRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        APPROVED = 'approved', 'Tasdiqlangan'
        PARTIAL = 'partial', "Qisman to'langan"
        PAID = 'paid', "To'liq to'langan"
        CANCELLED = 'cancelled', 'Bekor qilingan'

    teacher = models.ForeignKey(
        'academics.Teacher',
        on_delete=models.PROTECT,
        related_name='salary_records',
        verbose_name="O'qituvchi"
    )
    period_month = models.DateField(
        help_text="Oylik hisob oyi (oyning birinchi kuni)",
        verbose_name="Hisob oyi"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Hisoblangan oylik maosh"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Holati"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_salaries',
        verbose_name="Tasdiqlagan Ega"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Tasdiqlangan vaqt"
    )
    notes = models.TextField(blank=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Oylik maosh hisobi"
        verbose_name_plural = "Oylik maosh hisoblari"
        ordering = ['-period_month', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['teacher', 'period_month'],
                name='unique_salary_per_teacher_month'
            )
        ]

    def __str__(self):
        return f"{self.teacher.full_name} | {self.period_month.strftime('%Y-%m')} | {self.amount} so'm ({self.get_status_display()})"

    @property
    def total_paid(self) -> Decimal:
        """
        Total salary amount disbursed and completed.
        """
        result = self.payments.filter(status='completed').aggregate(total=Sum('amount'))['total']
        return result or Decimal('0.00')

    @property
    def remaining_balance(self) -> Decimal:
        """
        Unpaid salary obligation.
        """
        if self.status == self.Status.CANCELLED:
            return Decimal('0.00')
        rem = self.amount - self.total_paid
        return max(Decimal('0.00'), rem)

    def refresh_status(self, save=True):
        if self.status == self.Status.CANCELLED:
            return self.status

        paid = self.total_paid
        if paid >= self.amount:
            self.status = self.Status.PAID
        elif paid > Decimal('0.00'):
            self.status = self.Status.PARTIAL
        elif self.approved_at:
            self.status = self.Status.APPROVED
        else:
            self.status = self.Status.PENDING

        if save:
            self.save(update_fields=['status', 'updated_at'])
        return self.status


class SalaryPayment(models.Model):
    class Method(models.TextChoices):
        CASH = 'cash', 'Naqd pul'
        CARD = 'card', 'Plastik karta'
        BANK_TRANSFER = 'bank_transfer', "Bank hisob raqami"

    class Status(models.TextChoices):
        COMPLETED = 'completed', "To'langan"
        CANCELLED = 'cancelled', 'Bekor qilingan (Storno)'

    salary_record = models.ForeignKey(
        SalaryRecord,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="Oylik hisob"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="To'langan summa"
    )
    paid_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="To'langan vaqt"
    )
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.CASH,
        verbose_name="To'lov usuli"
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Kvitansiya / Hujjat raqami"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
        verbose_name="Holati"
    )
    cancellation_reason = models.TextField(
        blank=True,
        verbose_name="Bekor qilish sababi"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Bekor qilingan vaqt"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="To'lovni amalga oshirgan"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "Ish haqi to'lovi"
        verbose_name_plural = "Ish haqi to'lovlari"
        ordering = ['-paid_at', '-created_at']

    def __str__(self):
        return f"{self.salary_record.teacher.full_name} | {self.amount} so'm | {self.paid_at.strftime('%Y-%m-%d')}"
