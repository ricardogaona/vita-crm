from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import BigIntegerField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import formats, timezone


QUANTITY_MESSAGE = "La cantidad tiene que ser mayor que cero."
PRICE_MESSAGE = "El precio no puede ser negativo."
CHARGE_MESSAGE = "El cargo adicional no puede ser negativo."
TOTAL_MESSAGE = "El total no puede ser negativo."
CLIENT_MISMATCH = "La clienta tiene que ser la de la reserva."


class PerformedServiceQuerySet(models.QuerySet):
    def for_client_search(self, query):
        from clients.models import Client

        text = (query or "").strip()
        if not text:
            return self
        return self.filter(client__in=Client.objects.search(text))

    def for_professional(self, professional_id):
        if not professional_id:
            return self
        return self.filter(professional_id=professional_id)

    def between(self, start, end):
        results = self
        if start is not None:
            results = results.filter(performed_at__date__gte=start)
        if end is not None:
            results = results.filter(performed_at__date__lte=end)
        return results


class PerformedService(models.Model):
    client = models.ForeignKey(
        "clients.Client",
        verbose_name="clienta",
        on_delete=models.PROTECT,
        related_name="performed_services",
    )
    reservation = models.OneToOneField(
        "reservations.Reservation",
        verbose_name="reserva",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="performed_service",
    )
    professional = models.ForeignKey(
        "professionals.Professional",
        verbose_name="profesional",
        on_delete=models.PROTECT,
        related_name="performed_services",
    )
    performed_at = models.DateTimeField("fecha de atención")
    additional_charge_gs = models.PositiveBigIntegerField(
        "cargo adicional",
        default=0,
        validators=[MinValueValidator(0, CHARGE_MESSAGE)],
    )
    additional_charge_description = models.CharField(
        "descripción del cargo",
        max_length=255,
        blank=True,
        default="",
    )
    total_price_gs = models.PositiveBigIntegerField(
        "total",
        default=0,
        editable=False,
        validators=[MinValueValidator(0, TOTAL_MESSAGE)],
    )
    notes = models.TextField("observaciones", blank=True, default="")
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    objects = PerformedServiceQuerySet.as_manager()

    class Meta:
        verbose_name = "atención"
        verbose_name_plural = "atenciones"
        ordering = ["-performed_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(additional_charge_gs__gte=0),
                name="performed_service_additional_charge_non_negative",
                violation_error_message=CHARGE_MESSAGE,
            ),
            models.CheckConstraint(
                condition=Q(total_price_gs__gte=0),
                name="performed_service_total_non_negative",
                violation_error_message=TOTAL_MESSAGE,
            ),
        ]

    def __str__(self):
        if self.performed_at is None:
            return str(self.client)
        when = timezone.localtime(self.performed_at)
        return f"{self.client} — {formats.date_format(when, 'j/n/Y H:i')}"

    def clean(self):
        super().clean()
        if not self.reservation_id:
            return
        reservation_client_id = self.reservation.client_id
        if self.client_id and self.client_id != reservation_client_id:
            raise ValidationError({"client": CLIENT_MISMATCH})
        self.client_id = reservation_client_id

    def save(self, *args, **kwargs):
        self.notes = (self.notes or "").strip()
        self.additional_charge_description = (self.additional_charge_description or "").strip()
        update_fields = kwargs.get("update_fields")
        super().save(*args, **kwargs)
        if update_fields is not None and "additional_charge_gs" not in update_fields:
            return
        self.recalculate_total()
        super().save(update_fields=["total_price_gs", "updated_at"])

    def recalculate_total(self):
        if self.pk is None:
            items_total = 0
        else:
            items_total = self.items.aggregate(
                total=Coalesce(
                    Sum(
                        F("unit_price_gs") * F("quantity"),
                        output_field=BigIntegerField(),
                    ),
                    0,
                )
            )["total"]
        self.total_price_gs = items_total + (self.additional_charge_gs or 0)
        return self.total_price_gs

    @property
    def services_subtotal_gs(self):
        return (self.total_price_gs or 0) - (self.additional_charge_gs or 0)


class PerformedServiceItem(models.Model):
    performed_service = models.ForeignKey(
        PerformedService,
        verbose_name="atención",
        on_delete=models.CASCADE,
        related_name="items",
    )
    service = models.ForeignKey(
        "services.Service",
        verbose_name="servicio",
        on_delete=models.PROTECT,
        related_name="performed_service_items",
    )
    unit_price_gs = models.PositiveBigIntegerField(
        "precio unitario",
        validators=[MinValueValidator(0, PRICE_MESSAGE)],
    )
    quantity = models.PositiveIntegerField(
        "cantidad",
        default=1,
        validators=[MinValueValidator(1, QUANTITY_MESSAGE)],
    )

    class Meta:
        verbose_name = "servicio de la atención"
        verbose_name_plural = "servicios de la atención"
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="performed_service_item_quantity_at_least_one",
                violation_error_message=QUANTITY_MESSAGE,
            ),
            models.CheckConstraint(
                condition=Q(unit_price_gs__gte=0),
                name="performed_service_item_unit_price_non_negative",
                violation_error_message=PRICE_MESSAGE,
            ),
        ]

    def __str__(self):
        return f"{self.service} × {self.quantity}"

    @property
    def line_total_gs(self):
        return (self.unit_price_gs or 0) * (self.quantity or 0)
