from django import forms
from .models import Student


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['full_name', 'phone', 'parent_phone', 'birth_date', 'joined_at', 'status', 'notes']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Familiya Ism Sharif'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+998 90 123 45 67'}),
            'parent_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+998 90 987 65 43'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'joined_at': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': "Qo'shimcha ma'lumotlar"}),
        }
        labels = {
            'full_name': "F.I.SH. (To'liq ism)",
            'phone': "Telefon raqami",
            'parent_phone': "Ota-onasi telefon raqami",
            'birth_date': "Tug'ilgan sanasi",
            'joined_at': "Markazga kelgan sana",
            'status': "Holati",
            'notes': "Izohlar",
        }
