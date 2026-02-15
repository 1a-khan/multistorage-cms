from django import forms

from .models import ProjectHub


class ProjectHubForm(forms.ModelForm):
    class Meta:
        model = ProjectHub
        fields = ['name', 'description']
