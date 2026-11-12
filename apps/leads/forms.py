from django import forms
from django.utils import timezone
from .models import Lead
from apps.academics.models import StudyGroup, Course
from apps.accounts.models import User


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['full_name', 'phone', 'course', 'source', 'assigned_to', 'status', 'notes']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ism va familiya'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+998 90 123 45 67'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'source': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Murojaat bo‘yicha qo‘shimcha ma’lumotlar...'}),
        }
        labels = {
            'full_name': "F.I.SH. (Ism va familiya)",
            'phone': "Telefon raqami",
            'course': "Qiziqqan kurs",
            'source': "Murojaat manbasi",
            'assigned_to': "Mas'ul xodim",
            'status': "Lid holati (Status)",
            'notes': "Kommentariy / Izoh",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = Course.objects.filter(is_active=True).order_by('name')
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'username')
        self.fields['course'].empty_label = "-- Kursni tanlang (Ixtiyoriy) --"
        self.fields['assigned_to'].empty_label = "-- Mas'ul xodimni tanlang (Ixtiyoriy) --"


class LeadConvertForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=StudyGroup.objects.none(),
        label="Qo‘shiladigan guruh",
        widget=forms.Select(attrs={'class': 'form-select', 'required': 'required'}),
        empty_label="-- Guruhni tanlang --"
    )
    start_date = forms.DateField(
        label="A'zolik boshlanish sanasi",
        initial=timezone.now().date,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'required': 'required'})
    )
    monthly_price = forms.DecimalField(
        label="Kelishilgan oylik to‘lov miqdori",
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Standart narx bo‘yicha'}),
        help_text="Bo‘sh qoldirilsa, tanlangan guruh kursining standart narxi belgilanadi."
    )
    parent_phone = forms.CharField(
        label="Ota-ona telefoni (ixtiyoriy)",
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+998 90 987 65 43'})
    )

    def __init__(self, *args, **kwargs):
        course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        groups = StudyGroup.objects.filter(is_active=True).select_related('course', 'teacher').order_by('name')
        if course:
            # Put matching course groups first or filter
            pass
        self.fields['group'].queryset = groups
