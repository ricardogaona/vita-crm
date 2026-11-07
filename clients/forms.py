from django import forms
from django.core.exceptions import ValidationError

from ui.forms import TablerModelForm

from .models import Client, SourceChoices


class ClientForm(TablerModelForm):
    class Meta:
        model = Client
        fields = [
            "first_name",
            "last_name",
            "identification_number",
            "tax_id",
            "tax_name",
            "phone",
            "email",
            "source",
            "referred_by",
            "first_contact_date",
            "marketing_consent",
            "notes",
            "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "referred_by": "Opcional. No puede ser ella misma.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        referred_by = self.fields["referred_by"]
        referred_by.queryset = Client.objects.all()
        if self.instance.pk:
            referred_by.queryset = referred_by.queryset.exclude(pk=self.instance.pk)
        referred_by.empty_label = "Sin referente"

        self.fields["source"].choices = [("", "Sin origen"), *SourceChoices.choices]

        contact = self.fields["first_contact_date"]
        contact.input_formats = ["%Y-%m-%d"]
        contact.widget.format = "%Y-%m-%d"
        contact.widget.attrs["type"] = "date"

    def clean_referred_by(self):
        referred_by = self.cleaned_data.get("referred_by")
        if referred_by and self.instance.pk and referred_by.pk == self.instance.pk:
            raise ValidationError("Una clienta no puede estar referida por sí misma.")
        return referred_by
