import uuid
from django import forms
from django.utils import timezone
from .models import Payment, MonthlyCharge
from apps.accounts.models import CenterSettings
from apps.students.models import Student
from apps.academics.models import Enrollment, StudyGroup


class PaymentForm(forms.ModelForm):
    charge = forms.ModelChoiceField(
        queryset=MonthlyCharge.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Muayyan oylik hisobga yo'naltirish (ixtiyoriy, tanlanmasa eski qarzlarga taqsimlanadi)"
    )

    class Meta:
        model = Payment
        fields = ['student', 'amount', 'method', 'paid_at', 'reference', 'idempotency_key']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 500000'}),
            'method': forms.Select(attrs={'class': 'form-select'}),
            'paid_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Chek raqami yoki kvitansiya'}),
            'idempotency_key': forms.HiddenInput(),
        }
        labels = {
            'student': "O'quvchi",
            'amount': "To'lov summasi (so'm)",
            'method': "To'lov usuli",
            'paid_at': "To'lov vaqti",
            'reference': "Kvitansiya / Chek raqami",
        }

    def __init__(self, *args, **kwargs):
        student_id = kwargs.pop('student_id', None)
        super().__init__(*args, **kwargs)

        if not self.initial.get('idempotency_key'):
            self.initial['idempotency_key'] = str(uuid.uuid4())

        if not self.initial.get('paid_at'):
            self.initial['paid_at'] = timezone.now().strftime('%Y-%m-%dT%H:%M')

        if student_id:
            self.fields['student'].initial = student_id
            self.fields['charge'].queryset = MonthlyCharge.objects.filter(
                student_id=student_id
            ).exclude(status__in=[MonthlyCharge.Status.PAID, MonthlyCharge.Status.CANCELLED]).order_by('billing_month')
        else:
            self.fields['charge'].queryset = MonthlyCharge.objects.exclude(
                status__in=[MonthlyCharge.Status.PAID, MonthlyCharge.Status.CANCELLED]
            ).order_by('billing_month')


class MonthlyChargeForm(forms.Form):
    enrollment = forms.ModelChoiceField(
        queryset=Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).select_related('student', 'group'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="O'quvchi va guruh (A'zolik)"
    )
    billing_month = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Hisob oyi (oyning 1-sanasi)"
    )
    proration_policy = forms.ChoiceField(
        choices=CenterSettings.ProrationPolicy.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="To'liq bo'lmagan oy hisoblash siyosati"
    )
    custom_amount = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': "Bo'sh qoldirilsa avtomatik hisoblanadi"}),
        label="Maxsus summa (ixtiyoriy)"
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="To'lov muddati (ixtiyoriy, bo'sh bo'lsa sozlamalardan olinadi)"
    )


class BulkChargesForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=StudyGroup.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Muayyan guruh uchun (bo'sh qoldirilsa hamma faol guruhlar uchun)"
    )
    billing_month = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Hisob oyi (oyning 1-sanasi)"
    )
    proration_policy = forms.ChoiceField(
        choices=CenterSettings.ProrationPolicy.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="To'liq bo'lmagan oy siyosati"
    )


class CancelReasonForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Bekor qilish sababini batafsil yozing'}),
        label="Bekor qilish sababi"
    )
