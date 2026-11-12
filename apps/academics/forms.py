from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Course, Teacher, TeacherSalaryRate, StudyGroup, GroupSchedule, Enrollment, EnrollmentPriceHistory
from apps.students.models import Student
from apps.accounts.widgets import DynamicSearchSelect


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'default_monthly_price', 'duration_months', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: Ingliz tili (IELTS)'}),
            'default_monthly_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '500000'}),
            'duration_months': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Kurs nomi',
            'default_monthly_price': 'Standart oylik narx (so\'m)',
            'duration_months': 'Davomiyligi (oy)',
            'description': 'Kurs haqida qisqacha tavsif',
            'is_active': 'Faol holatda',
        }


class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ['full_name', 'phone', 'specialization', 'hire_date', 'status']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "O'qituvchi F.I.SH."}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+998 90 123 45 67'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Matematika, Rus tili'}),
            'hire_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'full_name': "F.I.SH.",
            'phone': "Telefon raqami",
            'specialization': "Mutaxassislik yo'nalishi",
            'hire_date': "Ishga qabul sanasi",
            'status': "Holati",
        }


class TeacherSalaryRateForm(forms.ModelForm):
    class Meta:
        model = TeacherSalaryRate
        fields = ['monthly_amount', 'valid_from', 'valid_to']
        widgets = {
            'monthly_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '3000000'}),
            'valid_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valid_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'monthly_amount': "Belgilangan oylik maosh (so'm)",
            'valid_from': "Amal qilish boshlanish sanasi",
            'valid_to': "Amal qilish tugash sanasi (agar ma'lum bo'lsa)",
        }


class StudyGroupForm(forms.ModelForm):
    class Meta:
        model = StudyGroup
        fields = ['name', 'course', 'teacher', 'capacity', 'start_date', 'end_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: IELTS 10:00 (Du-Chor-Ju)'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'teacher': DynamicSearchSelect(
                search_url='/api/search/teachers/',
                model=Teacher,
                placeholder="O'qituvchini qidirish (kamida 3 ta harf)..."
            ),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': "Guruh nomi",
            'course': "Kurs",
            'teacher': "O'qituvchi",
            'capacity': "Xona sig'imi (o'quvchi)",
            'start_date': "Mashg'ulotlar boshlanish sanasi",
            'end_date': "Tugash sanasi",
            'is_active': "Guruh faol",
        }


class GroupScheduleForm(forms.ModelForm):
    class Meta:
        model = GroupSchedule
        fields = ['weekday', 'start_time', 'end_time', 'room', 'is_active']
        widgets = {
            'weekday': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'room': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '2-xona'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'weekday': "Hafta kuni",
            'start_time': "Boshlanish vaqti",
            'end_time': "Tugash vaqti",
            'room': "Auditoriya / Xona",
            'is_active': "Faol holatda",
        }


class GroupScheduleMultiSlotForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=StudyGroup.objects.filter(is_active=True).order_by('name'),
        label="Guruh",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Guruhni tanlang --"
    )
    weekdays = forms.MultipleChoiceField(
        choices=GroupSchedule.Weekday.choices,
        label="Hafta kunlari",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    start_time = forms.TimeField(
        label="Boshlanish vaqti",
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'})
    )
    end_time = forms.TimeField(
        label="Tugash vaqti",
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'})
    )
    room = forms.CharField(
        label="Xona / Auditoriya",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 102-xona'})
    )
    is_active = forms.BooleanField(
        label="Faol holatda",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        if start and end and end <= start:
            raise ValidationError("Dars tugash vaqti boshlanish vaqtidan kechroq bo'lishi shart.")
        return cleaned_data


class LessonGenerateForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=StudyGroup.objects.filter(is_active=True).order_by('name'),
        required=False,
        label="Guruh",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Barcha faol guruhlar uchun --"
    )
    start_date = forms.DateField(
        label="Boshlanish sanasi",
        initial=timezone.now().date,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        label="Tugash sanasi",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and end < start:
            raise ValidationError("Tugash sanasi boshlanish sanasidan oldin bo'lishi mumkin emas.")
        return cleaned_data


class EnrollmentPriceUpdateForm(forms.Form):
    monthly_price = forms.DecimalField(
        label="Yangi individual oylik narx (so'm)",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 350000'})
    )
    reason_category = forms.ChoiceField(
        choices=EnrollmentPriceHistory.ReasonCategory.choices,
        label="O'zgartirish sababi",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    reason_details = forms.CharField(
        label="Qo'shimcha izoh / asos",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: Rahbar buyrug‘i №12 yoki 20% chegirma'})
    )
    update_current_unpaid_charge = forms.BooleanField(
        label="Joriy oydagi to'lanmagan oylik hisobni yangi narxga moslashtirish (to'langan hisoblar o'zgarmaydi)",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['student', 'group', 'start_date', 'monthly_price', 'payment_status']
        widgets = {
            'student': DynamicSearchSelect(
                search_url='/api/search/students/',
                model=Student,
                placeholder="O'quvchini qidirish (kamida 3 ta harf)..."
            ),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'monthly_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': "Bo'sh qoldirilsa kurs narxi olinadi"}),
            'payment_status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'student': "O'quvchi",
            'group': "Guruh",
            'start_date': "Boshlash sanasi",
            'monthly_price': "Kelishilgan oylik narx (so'm)",
            'payment_status': "To‘lov holati",
        }

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        group = cleaned_data.get('group')

        if student and group:
            existing = Enrollment.objects.filter(
                student=student,
                group=group,
                status=Enrollment.Status.ACTIVE
            ).exists()
            if existing:
                raise ValidationError(f"{student.full_name} allaqachon '{group.name}' guruhida faol o'quvchi!")

        return cleaned_data


class TransferEnrollmentForm(forms.Form):
    new_group = forms.ModelChoiceField(
        queryset=StudyGroup.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Ko'chirilayotgan yangi guruh"
    )
    transfer_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Ko'chirish sanasi"
    )
    new_monthly_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': "Yangi narx (ixtiyoriy)"}),
        label="Yangi kelishilgan oylik narx (so'm)"
    )
