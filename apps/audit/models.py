from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = 'CREATE', 'Yaratish'
        UPDATE = 'UPDATE', "O'zgartirish"
        DELETE = 'DELETE', "O'chirish / Arxivlash"
        CANCEL = 'CANCEL', 'Bekor qilish (Storno)'
        PAYMENT = 'PAYMENT', "To'lov o'tkazish"
        SALARY = 'SALARY', "Ish haqi amaliyoti"
        APPROVE = 'APPROVE', 'Tasdiqlash'
        STATUS_CHANGE = 'STATUS_CHANGE', "Holat o'zgarishi"
        LOGIN = 'LOGIN', 'Tizimga kirish'

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Bajaruvchi"
    )
    action = models.CharField(
        max_length=50,
        choices=Action.choices,
        verbose_name="Harakat turi"
    )
    entity_type = models.CharField(
        max_length=100,
        verbose_name="Ob'ekt turi"
    )
    entity_id = models.CharField(
        max_length=100,
        verbose_name="Ob'ekt ID"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Vaqt"
    )
    changes_before = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Oldingi holat"
    )
    changes_after = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Keyingi holat"
    )
    reason = models.TextField(
        blank=True,
        verbose_name="Sabab / Izoh"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP manzil"
    )

    class Meta:
        verbose_name = "Audit jurnali"
        verbose_name_plural = "Audit jurnallari"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['action']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        actor_name = self.actor.username if self.actor else "Tizim"
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} | {actor_name} | {self.action} | {self.entity_type} #{self.entity_id}"
