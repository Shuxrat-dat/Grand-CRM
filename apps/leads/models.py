from django.db import models
from django.conf import settings
from django.utils import timezone


class Lead(models.Model):
    class Status(models.TextChoices):
        YANGI = 'yangi', 'Yangi'
        BOGLANILDI = 'boglanildi', 'Bog‘lanildi'
        SINOV_DARSI = 'sinov_darsi', 'Sinov darsiga yozildi'
        KUTILMOQDA = 'kutilmoqda', 'Kutilmoqda'
        KELMAGAN = 'kelmagan', 'Kelmagan'
        QAYTA_ALOQA = 'qayta_aloqa', 'Qayta aloqa'
        CONVERTED = 'converted', 'O‘quvchiga aylantirildi'
        RAD_ETDI = 'rad_etdi', 'Rad etdi'

    class Source(models.TextChoices):
        PERSONAL = 'personal', 'Shaxsan'
        PHONE = 'phone', 'Telefon'
        TELEGRAM = 'telegram', 'Telegram'
        INSTAGRAM = 'instagram', 'Instagram'
        ADVERTISING = 'advertising', 'Reklama'
        RECOMMENDATION = 'recommendation', 'Tavsiya'
        OTHER = 'other', 'Boshqa'

    full_name = models.CharField(max_length=255, verbose_name="F.I.SH.")
    phone = models.CharField(max_length=30, verbose_name="Telefon raqami")
    course = models.ForeignKey(
        'academics.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
        verbose_name="Qiziqqan kurs"
    )
    source = models.CharField(
        max_length=30,
        choices=Source.choices,
        default=Source.PHONE,
        verbose_name="Murojaat manbasi"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Murojaat sanasi"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Yangilangan vaqt"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Izoh / Kommentariy"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads',
        verbose_name="Mas'ul xodim"
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.YANGI,
        verbose_name="Holati"
    )
    converted_student = models.OneToOneField(
        'students.Student',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_source',
        verbose_name="Yaratilgan o‘quvchi"
    )
    converted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Aylantirilgan sana"
    )
    converted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_leads',
        verbose_name="Aylantirgan xodim"
    )

    class Meta:
        verbose_name = "Lid"
        verbose_name_plural = "Lidlar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['phone']),
            models.Index(fields=['created_at']),
            models.Index(fields=['source']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone}) - {self.get_status_display()}"

    @property
    def is_converted(self):
        return self.status == self.Status.CONVERTED or self.converted_student_id is not None
