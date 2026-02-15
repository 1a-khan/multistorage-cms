from django import forms
from django.db.models import Q

from storage_backends.models import StorageBackend

from .models import Document


class DocumentUploadForm(forms.ModelForm):
    file = forms.FileField()
    storage_backend = forms.ModelChoiceField(queryset=StorageBackend.objects.none())

    class Meta:
        model = Document
        fields = ['title', 'description', 'visibility', 'storage_backend', 'file']

    def __init__(self, *args, project_hub=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['storage_backend'].queryset = StorageBackend.objects.filter(
            Q(project_hub=project_hub) | Q(project_hub__isnull=True),
            status=StorageBackend.Status.ACTIVE,
        ).order_by('name')
