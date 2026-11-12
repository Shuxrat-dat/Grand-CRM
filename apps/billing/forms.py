import uuid
from django import forms
from django.utils import timezone
from .models import Payment, MonthlyCharge
from apps.accounts.models import CenterSettings
from apps.students.models import Student
from apps.academics.models import Enrollment, StudyGroup
from apps.accounts.widgets import DynamicSearchSelect


class PaymentForm(forms.ModelForm):
    charge = forms.ModelChoiceField(
        queryset=MonthlyCharge.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Muayyan oylik hisobga yo'naltirish (ixtiyoriy, tanlanmasa eski qarzlarga taqsimlanadi)"
    )

    class Meta:
        model = Payment
        fields = ['student', 'group', 'amount', 'method', 'paid_at', 'idempotency_key']
        widgets = {
            'student': DynamicSearchSelect(
                search_url='/api/search/students/',
                model=Student,
                placeholder="O'quvchini qidirish (kamida 3 ta harf)..."
            ),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 500000'}),
            'method': forms.Select(attrs={'class': 'form-select'}),
            'paid_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'idempotency_key': forms.HiddenInput(),
        }
        labels = {
            'student': "O'quvchi",
            'amount': "To'lov summasi (so'm)",
            'method': "To'lov usuli",
            'paid_at': "To'lov vaqti",
            'group': "Guruh",
        }

    def __init__(self, *args, **kwargs):
        student_id = kwargs.pop('student_id', None)
        super().__init__(*args, **kwargs)

        if not self.initial.get('idempotency_key'):
            self.initial['idempotency_key'] = str(uuid.uuid4())

        if not self.initial.get('paid_at'):
            self.initial['paid_at'] = timezone.now().strftime('%Y-%m-%dT%H:%M')

        self.fields['group'].required = True
        self.fields['group'].empty_label = "- Guruhni tanlang -"

        if student_id:
            self.fields['student'].initial = student_id
            self.fields['group'].queryset = StudyGroup.objects.filter(
                enrollments__student_id=student_id,
                enrollments__status=Enrollment.Status.ACTIVE,
            ).distinct().order_by('name')
            self.fields['charge'].queryset = MonthlyCharge.objects.filter(
                student_id=student_id
            ).exclude(status__in=[MonthlyCharge.Status.PAID, MonthlyCharge.Status.CANCELLED]).order_by('billing_month')
        else:
            self.fields['group'].queryset = StudyGroup.objects.filter(is_active=True).order_by('name')
            self.fields['charge'].queryset = MonthlyCharge.objects.exclude(
                status__in=[MonthlyCharge.Status.PAID, MonthlyCharge.Status.CANCELLED]
            ).order_by('billing_month')

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get('student')
        group = cleaned.get('group')
        if student and group and not Enrollment.objects.filter(
            student=student, group=group, status=Enrollment.Status.ACTIVE
        ).exists():
            self.add_error('group', "Bu o'quvchi tanlangan guruhda o'qimaydi.")
        return cleaned


class MonthlyChargeForm(forms.Form):
    enrollment = forms.ModelChoiceField(
        queryset=Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).select_related('student', 'group'),
        widget=DynamicSearchSelect(
            search_url='/api/search/enrollments/',
            model=Enrollment,
            placeholder="O'quvchi yoki guruh nomi (kamida 3 ta harf)..."
        ),
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
