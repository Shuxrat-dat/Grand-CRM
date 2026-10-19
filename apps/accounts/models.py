from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Ega (Owner)'
        ADMIN = 'ADMIN', 'Administrator'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ADMIN,
        verbose_name="Rol"
    )
    phone = models.CharField(max_length=30, blank=True, verbose_name="Telefon")

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER or self.is_superuser

    @property
    def is_admin_staff(self):
        return self.role in [self.Role.ADMIN, self.Role.OWNER] or self.is_staff

    def __str__(self):
        full = self.get_full_name()
        return full if full else self.username


class CenterSettings(models.Model):
    class ProrationPolicy(models.TextChoices):
        FULL_MONTH = 'FULL_MONTH', "To'liq oylik to'lov (Full month)"
        PROPORTIONAL = 'PROPORTIONAL', "Kunlarga proporsional (Proportional)"

    center_name = models.CharField(
        max_length=200,
        default="Grand Ta'lim Markazi",
        verbose_name="O'quv markazi nomi"
    )
    proration_policy = models.CharField(
        max_length=20,
        choices=ProrationPolicy.choices,
        default=ProrationPolicy.FULL_MONTH,
        verbose_name="To'liq bo'lmagan oy siyosati"
    )
    payment_due_day = models.PositiveSmallIntegerField(
        default=5,
        verbose_name="Har oylik to'lov muddati (kun)"
    )
    currency = models.CharField(
        max_length=10,
        default="UZS",
        verbose_name="Valyuta"
    )
    phone = models.CharField(max_length=30, blank=True, verbose_name="Markaz telefoni")
    address = models.CharField(max_length=255, blank=True, verbose_name="Manzil")

    class Meta:
        verbose_name = "Tizim sozlamalari"
        verbose_name_plural = "Tizim sozlamalari"

    def __str__(self):
        return self.center_name

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
