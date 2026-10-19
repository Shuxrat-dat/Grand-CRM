from django import forms
from django.utils import timezone
from .models import SalaryPayment
from apps.academics.models import Teacher


class SalaryGenerateForm(forms.Form):
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.filter(status=Teacher.Status.ACTIVE),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="O'qituvchi"
    )
    period_month = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Hisob oyi (oyning 1-sanasi)"
    )
    custom_amount = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': "Bo'sh bo'lsa o'qituvchi stavkasi olinadi"}),
        label="Maxsus summa (ixtiyoriy)"
    )


class BulkSalaryGenerateForm(forms.Form):
    period_month = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Hisob oyi (oyning 1-sanasi)"
    )


class SalaryPaymentForm(forms.ModelForm):
    allow_overpay = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Qarzdorlikdan ortiqcha to'lovga ruxsat berish (mukofot / avans)"
    )

    class Meta:
        model = SalaryPayment
        fields = ['amount', 'method', 'paid_at', 'reference']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 3000000'}),
            'method': forms.Select(attrs={'class': 'form-select'}),
            'paid_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Hujjat raqami'}),
        }
        labels = {
            'amount': "To'lov summasi (so'm)",
            'method': "To'lov usuli",
            'paid_at': "To'lov sanasi va vaqti",
            'reference': "Kvitansiya / Chek raqami",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('paid_at'):
            self.initial['paid_at'] = timezone.now().strftime('%Y-%m-%dT%H:%M')
