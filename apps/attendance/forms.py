from django import forms
from .models import Lesson, AttendanceRecord
from apps.academics.models import StudyGroup


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['group', 'date', 'starts_at', 'ends_at', 'topic', 'status']
        widgets = {
            'group': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'starts_at': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'ends_at': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dars mavzusi'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'group': "Guruh",
            'date': "Dars sanasi",
            'starts_at': "Boshlanish vaqti",
            'ends_at': "Tugash vaqti",
            'topic': "Dars mavzusi",
            'status': "Dars holati",
        }
