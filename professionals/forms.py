from django import forms

from ui.forms import TablerModelForm

from .models import Professional


class ProfessionalDateInput(forms.DateInput):
    input_type = "date"


class ProfessionalForm(TablerModelForm):
    text_fields = (
        "first_name",
        "last_name",
        "identification_number",
        "phone",
        "email",
        "notes",
    )

    class Meta:
        model = Professional
        fields = [
            "first_name",
            "last_name",
            "identification_number",
            "phone",
            "email",
            "is_active",
            "start_date",
            "end_date",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "start_date": ProfessionalDateInput(format="%Y-%m-%d"),
            "end_date": ProfessionalDateInput(format="%Y-%m-%d"),
        }
        error_messages = {
            "first_name": {"required": "Indicá el nombre."},
            "last_name": {"required": "Indicá el apellido."},
            "identification_number": {"required": "Indicá el documento."},
            "phone": {"required": "Indicá el teléfono."},
            "email": {"required": "Indicá el correo electrónico."},
        }
        help_texts = {
            "end_date": "Opcional. Si la cargás, tiene que ser igual o posterior a la incorporación.",
            "is_active": "Desmarcala para pausarla. La ficha sigue en el historial.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("start_date", "end_date"):
            self.fields[name].input_formats = ["%Y-%m-%d"]
        self._errors = None

    def full_clean(self):
        if self.is_bound:
            data = self.data.copy()
            for name in self.text_fields:
                value = data.get(name)
                if isinstance(value, str):
                    data[name] = value.strip()
            self.data = data
        super().full_clean()
