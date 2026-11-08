from django import forms
from django.db.models import Q
from django.forms.models import BaseInlineFormSet, inlineformset_factory

from clients.models import Client
from professionals.models import Professional
from reservations.models import Reservation
from services.models import Service
from ui.forms import TablerModelForm

from .models import (
    PRICE_MESSAGE,
    QUANTITY_MESSAGE,
    PerformedService,
    PerformedServiceItem,
)

RESERVATION_REQUIRED = "Indicá la reserva."
RESERVATION_TAKEN = "Esa reserva ya tiene una atención."
CLIENT_REQUIRED = "Indicá la clienta."
PROFESSIONAL_REQUIRED = "Indicá la profesional."
PERFORMED_AT_REQUIRED = "Indicá la fecha y hora de la atención."
INACTIVE_PROFESSIONAL = "Elegí una profesional activa."
INACTIVE_SERVICE = "Ese servicio no está activo."
SERVICE_REQUIRED = "Elegí un servicio."
ITEMS_REQUIRED = "Agregá al menos un servicio."

DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
DATETIME_INPUT_FORMATS = [DATETIME_FORMAT, "%Y-%m-%dT%H:%M:%S"]


class PerformedServiceDateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"


class PerformedServiceForm(TablerModelForm):
    has_reservation = forms.BooleanField(
        required=False,
        label="¿Tiene reserva?",
        initial=True,
    )

    class Meta:
        model = PerformedService
        fields = (
            "reservation",
            "client",
            "professional",
            "performed_at",
            "notes",
            "additional_charge_gs",
            "additional_charge_description",
        )
        widgets = {
            "reservation": forms.HiddenInput(),
            "client": forms.HiddenInput(),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "performed_at": PerformedServiceDateTimeInput(format=DATETIME_FORMAT),
            "additional_charge_description": forms.TextInput(),
        }
        error_messages = {
            "reservation": {"invalid_choice": "Elegí una reserva válida."},
            "client": {"invalid_choice": "Elegí una clienta válida."},
            "professional": {
                "required": PROFESSIONAL_REQUIRED,
                "invalid_choice": "Elegí una profesional válida.",
            },
            "performed_at": {
                "required": PERFORMED_AT_REQUIRED,
                "invalid": "Indicá una fecha y hora válidas.",
            },
            "additional_charge_gs": {
                "required": "Indicá el cargo adicional.",
                "invalid": "Indicá un importe válido.",
                "min_value": PRICE_MESSAGE,
            },
        }
        help_texts = {
            "performed_at": "Fecha y hora en que se realizó la atención.",
            "additional_charge_gs": "Importe extra que no está en el catálogo. Empezá en 0 si no hay.",
            "additional_charge_description": "Por ejemplo, diseño personalizado.",
        }
        labels = {
            "additional_charge_gs": "Cargo adicional",
            "additional_charge_description": "Descripción del cargo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        performed_at = self.fields["performed_at"]
        performed_at.input_formats = DATETIME_INPUT_FORMATS
        performed_at.widget.format = DATETIME_FORMAT
        self.fields["additional_charge_gs"].initial = 0
        self.fields["client"].required = False
        self.fields["client"].queryset = Client.objects.all()
        self.fields["reservation"].required = False
        reservation_filter = Q(performed_service__isnull=True)
        if self.instance.pk and self.instance.reservation_id:
            reservation_filter |= Q(pk=self.instance.reservation_id)
        self.fields["reservation"].queryset = Reservation.objects.filter(reservation_filter)
        professionals = Professional.objects.filter(is_active=True)
        if self.instance.pk and self.instance.professional_id:
            professionals = Professional.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.professional_id)
            )
        self.fields["professional"].queryset = professionals
        self.fields["professional"].empty_label = "Elegí una profesional"
        if self.instance.pk:
            self.fields["has_reservation"].initial = bool(self.instance.reservation_id)
        else:
            self.fields["has_reservation"].initial = True
        # El estilo consulta los errores y valida antes de estos ajustes.
        self._errors = None

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("has_reservation"):
            if "reservation" not in self.errors and not cleaned.get("reservation"):
                self.add_error("reservation", RESERVATION_REQUIRED)
            reservation = cleaned.get("reservation")
            if reservation is not None:
                taken = PerformedService.objects.filter(reservation=reservation)
                if self.instance.pk:
                    taken = taken.exclude(pk=self.instance.pk)
                if taken.exists():
                    self.add_error("reservation", RESERVATION_TAKEN)
                else:
                    cleaned["client"] = reservation.client
        else:
            cleaned["reservation"] = None
            if "client" not in self.errors and not cleaned.get("client"):
                self.add_error("client", CLIENT_REQUIRED)
        professional = cleaned.get("professional")
        if professional and not professional.is_active:
            if not self.instance.pk or self.instance.professional_id != professional.pk:
                self.add_error("professional", INACTIVE_PROFESSIONAL)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("has_reservation"):
            instance.reservation = self.cleaned_data["reservation"]
            instance.client = instance.reservation.client
        else:
            instance.reservation = None
            instance.client = self.cleaned_data["client"]
        if commit:
            instance.save()
        return instance


class PerformedServiceItemForm(TablerModelForm):
    class Meta:
        model = PerformedServiceItem
        fields = ("service", "unit_price_gs", "quantity")
        widgets = {
            "service": forms.HiddenInput(),
            "unit_price_gs": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": 1,
                    "inputmode": "numeric",
                    "readonly": True,
                    "data-unit-price": "true",
                }
            ),
            "quantity": forms.NumberInput(
                attrs={"min": 1, "step": 1, "inputmode": "numeric", "data-quantity": "true"}
            ),
        }
        error_messages = {
            "service": {
                "required": SERVICE_REQUIRED,
                "invalid_choice": "Elegí un servicio válido.",
            },
            "unit_price_gs": {
                "invalid": "Indicá un precio válido.",
                "min_value": PRICE_MESSAGE,
            },
            "quantity": {
                "required": "Indicá la cantidad.",
                "invalid": "Indicá una cantidad válida.",
                "min_value": QUANTITY_MESSAGE,
            },
        }
        help_texts = {
            "unit_price_gs": "Queda guardado aunque después cambie el catálogo.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        services = Service.objects.filter(is_active=True)
        if self.instance.pk and self.instance.service_id:
            services = Service.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.service_id)
            )
        self.fields["service"].queryset = services
        self.fields["quantity"].initial = 1
        self.fields["unit_price_gs"].required = False
        self.selected_service = self._selected_service()
        self._errors = None

    def _selected_service(self):
        raw = self["service"].value()
        if raw in (None, ""):
            return None
        return self.fields["service"].queryset.filter(pk=raw).first()

    def clean(self):
        cleaned = super().clean()
        service = cleaned.get("service")
        if service is None:
            return cleaned
        if not service.is_active and (
            not self.instance.pk or self.instance.service_id != service.pk
        ):
            self.add_error("service", INACTIVE_SERVICE)
        price = cleaned.get("unit_price_gs")
        same_service = self.instance.pk and self.instance.service_id == service.pk
        service_changed = self.instance.pk and self.instance.service_id != service.pk
        if service_changed and price == self.instance.unit_price_gs:
            price = service.price_gs
        elif price is None and not same_service:
            price = service.price_gs
        elif price is None and same_service:
            price = self.instance.unit_price_gs
        if price is None:
            self.add_error("unit_price_gs", "Indicá el precio unitario.")
        else:
            cleaned["unit_price_gs"] = price
        return cleaned


class BasePerformedServiceItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return
        kept = 0
        for form in self.forms:
            data = getattr(form, "cleaned_data", None)
            if not data or data.get("DELETE"):
                continue
            kept += 1
        if kept < 1:
            raise forms.ValidationError(ITEMS_REQUIRED)


def build_item_formset(data=None, instance=None, extra=None):
    if extra is None:
        extra = 0 if data is not None or (instance and instance.pk) else 1
    formset_class = inlineformset_factory(
        PerformedService,
        PerformedServiceItem,
        form=PerformedServiceItemForm,
        formset=BasePerformedServiceItemFormSet,
        extra=extra,
        can_delete=True,
        max_num=30,
        validate_max=True,
    )
    return formset_class(data, instance=instance)
