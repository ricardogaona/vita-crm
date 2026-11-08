from django import forms

from ui.forms import TablerModelForm

from .models import Reservation


class ReservationDateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"


DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
DATETIME_INPUT_FORMATS = [DATETIME_FORMAT, "%Y-%m-%dT%H:%M:%S"]


class ReservationForm(TablerModelForm):
    class Meta:
        model = Reservation
        fields = [
            "client",
            "scheduled_at",
            "status",
            "attended_at",
            "notes",
        ]
        widgets = {
            "client": forms.HiddenInput(),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "scheduled_at": ReservationDateTimeInput(format=DATETIME_FORMAT),
            "attended_at": ReservationDateTimeInput(format=DATETIME_FORMAT),
        }
        error_messages = {
            "client": {
                "required": "Indicá la clienta.",
                "invalid_choice": "Elegí una clienta válida.",
            },
            "scheduled_at": {
                "required": "Indicá la fecha y hora.",
                "invalid": "Indicá una fecha y hora válidas.",
            },
            "status": {"invalid_choice": "Elegí un estado válido."},
            "attended_at": {"invalid": "Indicá una fecha y hora válidas."},
        }
        help_texts = {
            "attended_at": "Opcional. Cuándo se atendió a la clienta.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("scheduled_at", "attended_at"):
            field = self.fields[name]
            field.input_formats = DATETIME_INPUT_FORMATS
            field.widget.format = DATETIME_FORMAT
