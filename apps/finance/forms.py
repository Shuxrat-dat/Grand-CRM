from django import forms
from django.utils import timezone
from .models import Expense


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['category', 'amount', 'occurred_at', 'method', 'description']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: 1200000'}),
            'occurred_at': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'method': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Xarajat sababi, tafsilotlari'}),
        }
        labels = {
            'category': "Xarajat toifasi",
            'amount': "Summa (so'm)",
            'occurred_at': "Xarajat sanasi",
            'method': "To'lov usuli",
            'description': "Tavsif / Izoh",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('occurred_at'):
            self.initial['occurred_at'] = timezone.now().date()
