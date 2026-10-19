from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum


class MonthlyCharge(models.Model):
    class Status(models.TextChoices):
        UNPAID = 'unpaid', "To'lanmagan"
        PARTIAL = 'partial', "Qisman to'langan"
        PAID = 'paid', "To'langan"
        OVERDUE = 'overdue', "Muddati o'tgan"
        CANCELLED = 'cancelled', 'Bekor qilingan'

    student = models.ForeignKey(
        'students.Student',
        on_delete=models.PROTECT,
        related_name='monthly_charges',
        verbose_name="O'quvchi"
    )
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        on_delete=models.PROTECT,
        related_name='charges',
        verbose_name="A'zolik"
    )
    billing_month = models.DateField(
        help_text="Oylik hisob-kitob oyi (oyning birinchi kuni)",
        verbose_name="Hisob oyi"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Hisoblangan summa"
    )
    due_date = models.DateField(verbose_name="To'lovning oxirgi muddati")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNPAID,
        verbose_name="Holati"
    )
    notes = models.TextField(blank=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Oylik to'lov hisobi (Charge)"
        verbose_name_plural = "Oylik to'lov hisoblari (Charges)"
        ordering = ['-billing_month', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'enrollment', 'billing_month'],
                name='unique_charge_per_student_enrollment_month'
            )
        ]

    def __str__(self):
        return f"{self.student.full_name} | {self.billing_month.strftime('%Y-%m')} | {self.amount} so'm ({self.get_status_display()})"

    @property
    def allocated_amount(self) -> Decimal:
        """
        Calculates the sum of all completed payment allocations.
        """
        result = self.allocations.filter(
            payment__status='completed'
        ).aggregate(total=Sum('amount'))['total']
        return result or Decimal('0.00')

    @property
    def remaining_balance(self) -> Decimal:
        """
        Remaining debt on this specific charge.
        """
        if self.status == self.Status.CANCELLED:
            return Decimal('0.00')
        rem = self.amount - self.allocated_amount
        return max(Decimal('0.00'), rem)

    def refresh_status(self, save=True):
        """
        Recalculates status based on payment allocations and due date.
        Cancelled charges stay cancelled.
        """
        if self.status == self.Status.CANCELLED:
            return self.status

        allocated = self.allocated_amount
        today = timezone.now().date()

        if allocated >= self.amount:
            self.status = self.Status.PAID
        elif allocated > Decimal('0.00'):
            self.status = self.Status.PARTIAL
        else:
            if self.due_date and today > self.due_date:
                self.status = self.Status.OVERDUE
            else:
                self.status = self.Status.UNPAID

        if save:
            self.save(update_fields=['status', 'updated_at'])
        return self.status


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = 'cash', 'Naqd pul'
        CARD = 'card', 'Plastik karta (Humo/Uzcard)'
        BANK_TRANSFER = 'bank_transfer', "Bank o'tkazmasi (Hisob raqam)"
        OTHER = 'other', 'Boshqa'

    class Status(models.TextChoices):
        COMPLETED = 'completed', 'Bajarilgan'
        CANCELLED = 'cancelled', 'Bekor qilingan (Storno)'

    student = models.ForeignKey(
        'students.Student',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="O'quvchi"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="To'lov summasi"
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
        verbose_name="Chek raqami / Tranzaksiya kodi"
    )
    idempotency_key = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        verbose_name="Idempotentlik kaliti"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
        verbose_name="To'lov holati"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_payments',
        verbose_name="Qabul qilgan xodim"
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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
        ordering = ['-paid_at', '-created_at']

    def __str__(self):
        return f"{self.student.full_name} | {self.amount} so'm ({self.get_method_display()}) | {self.paid_at.strftime('%Y-%m-%d')}"

    @property
    def allocated_amount(self) -> Decimal:
        """
        Total amount allocated to non-cancelled charges.
        """
        if self.status == self.Status.CANCELLED:
            return Decimal('0.00')
        result = self.allocations.exclude(
            charge__status='cancelled'
        ).aggregate(total=Sum('amount'))['total']
        return result or Decimal('0.00')

    @property
    def unallocated_amount(self) -> Decimal:
        """
        Remaining unallocated amount (prepayment/excess).
        """
        if self.status == self.Status.CANCELLED:
            return Decimal('0.00')
        unalloc = self.amount - self.allocated_amount
        return max(Decimal('0.00'), unalloc)


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name="To'lov"
    )
    charge = models.ForeignKey(
        MonthlyCharge,
        on_delete=models.PROTECT,
        related_name='allocations',
        verbose_name="Oylik hisob (Charge)"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Taqsimlangan summa"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")

    class Meta:
        verbose_name = "To'lov taqsimoti"
        verbose_name_plural = "To'lov taqsimotlari"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=Decimal('0.00')),
                name='allocation_amount_gt_zero'
            )
        ]

    def __str__(self):
        return f"Allocation: {self.amount} so'm from Payment #{self.payment_id} to Charge #{self.charge_id}"
