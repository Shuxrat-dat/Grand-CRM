from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.db.models import Sum


class Student(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Faol'
        SUSPENDED = 'suspended', 'Muzlatilgan'
        COMPLETED = 'completed', 'Bitirgan'
        ARCHIVED = 'archived', 'Arxivlangan'

    full_name = models.CharField(max_length=255, verbose_name="F.I.SH.")
    phone = models.CharField(max_length=30, verbose_name="Telefon raqami")
    parent_phone = models.CharField(max_length=30, blank=True, verbose_name="Ota-onasi telefoni")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sana")
    joined_at = models.DateField(default=timezone.now, verbose_name="Qo'shilgan sana")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Holati"
    )
    notes = models.TextField(blank=True, verbose_name="Qo'shimcha izohlar")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        verbose_name = "O'quvchi"
        verbose_name_plural = "O'quvchilar"
        ordering = ['full_name']
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['phone']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    @property
    def total_charged(self) -> Decimal:
        """
        Total amount charged (excluding cancelled charges).
        """
        result = self.monthly_charges.exclude(status='cancelled').aggregate(total=Sum('amount'))['total']
        return result or Decimal('0.00')

    @property
    def total_payments_received(self) -> Decimal:
        """
        Total cash/bank payments received and completed.
        """
        result = self.payments.filter(status='completed').aggregate(total=Sum('amount'))['total']
        return result or Decimal('0.00')

    @property
    def total_allocated_payments(self) -> Decimal:
        """
        Total payment amount applied to active monthly charges.
        """
        from apps.billing.models import PaymentAllocation
        result = PaymentAllocation.objects.filter(
            payment__student=self,
            payment__status='completed',
            charge__student=self
        ).exclude(charge__status='cancelled').aggregate(total=Sum('amount'))['total']
        return result or Decimal('0.00')

    @property
    def total_debt(self) -> Decimal:
        """
        Remaining unpaid amount across all non-cancelled charges.
        Debt = Total Charged - Total Allocated Payments.
        """
        debt = self.total_charged - self.total_allocated_payments
        return max(Decimal('0.00'), debt)

    @property
    def prepayment_balance(self) -> Decimal:
        """
        Excess money paid that is not yet allocated to any charges.
        Prepayment = Total Completed Payments - Total Allocated Payments.
        """
        prepay = self.total_payments_received - self.total_allocated_payments
        return max(Decimal('0.00'), prepay)

    @property
    def active_enrollments(self):
        return self.enrollments.filter(status='active').select_related('group', 'group__course', 'group__teacher')
