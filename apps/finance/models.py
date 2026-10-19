from django.db import models
from django.conf import settings
from django.utils import timezone


class Expense(models.Model):
    class Category(models.TextChoices):
        RENT = 'rent', 'Bino ijarasi'
        UTILITIES = 'utilities', 'Kommunal xizmatlar'
        MARKETING = 'marketing', 'Marketing va reklama'
        EQUIPMENT = 'equipment', 'Jihozlar va uskunalar'
        SUPPLIES = 'supplies', 'Kantselyariya va xomashyo'
        TAX = 'tax', 'Soliqlar va majburiy to‘lovlar'
        OTHER = 'other', 'Boshqa xarajatlar'

    class Method(models.TextChoices):
        CASH = 'cash', 'Naqd pul'
        CARD = 'card', 'Karta'
        BANK_TRANSFER = 'bank_transfer', "Bank o'tkazmasi"
        OTHER = 'other', 'Boshqa'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Faol'
        CANCELLED = 'cancelled', 'Bekor qilingan'

    category = models.CharField(
        max_length=50,
        choices=Category.choices,
        default=Category.OTHER,
        verbose_name="Xarajat toifasi"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Summa"
    )
    occurred_at = models.DateField(
        default=timezone.now,
        verbose_name="Xarajat sanasi"
    )
    description = models.TextField(verbose_name="Tavsif / Maqsad")
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.CASH,
        verbose_name="To'lov usuli"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
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
        related_name='expenses',
        verbose_name="Kiritgan xodim"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Xarajat"
        verbose_name_plural = "Xarajatlar"
        ordering = ['-occurred_at', '-created_at']

    def __str__(self):
        return f"{self.get_category_display()} | {self.amount} so'm | {self.occurred_at.strftime('%Y-%m-%d')}"
