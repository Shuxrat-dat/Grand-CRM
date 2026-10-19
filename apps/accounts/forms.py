from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from .models import User, CenterSettings


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Foydalanuvchi nomi'}),
        label="Foydalanuvchi nomi"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Parol'}),
        label="Parol"
    )


class AdminUserForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Yangi parol (ixtiyoriy)'}),
        label="Parol"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'phone', 'email', 'is_active', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'username': 'Foydalanuvchi nomi (login)',
            'first_name': 'Ism',
            'last_name': 'Familiya',
            'phone': 'Telefon raqam',
            'email': 'Elektron pochta',
            'role': 'Tizimdagi roli',
            'is_active': 'Faol holatda',
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class CenterSettingsForm(forms.ModelForm):
    class Meta:
        model = CenterSettings
        fields = ['center_name', 'proration_policy', 'payment_due_day', 'currency', 'phone', 'address']
        widgets = {
            'center_name': forms.TextInput(attrs={'class': 'form-control'}),
            'proration_policy': forms.Select(attrs={'class': 'form-select'}),
            'payment_due_day': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 31}),
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'center_name': "O'quv markazi nomi",
            'proration_policy': "To'liq bo'lmagan oy hisoblash siyosati",
            'payment_due_day': "Oylik to'lov muddati (sana)",
            'currency': "Valyuta belgisi",
            'phone': "Aloqa telefoni",
            'address': "Manzil",
        }
