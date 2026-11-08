from django.db import models
from django.utils import formats, timezone


class StatusChoices(models.TextChoices):
    PENDING = "pending", "Pendiente"
    CONFIRMED = "confirmed", "Confirmada"
    ATTENDED = "attended", "Atendida"
    CANCELLED = "cancelled", "Cancelada"
    NO_SHOW = "no_show", "Ausente"


class ReservationQuerySet(models.QuerySet):
    def for_client_search(self, query):
        from clients.models import Client

        text = (query or "").strip()
        if not text:
            return self
        return self.filter(client__in=Client.objects.search(text))

    def by_status(self, status):
        if status in StatusChoices.values:
            return self.filter(status=status)
        return self

    def on_date(self, day):
        if day is None:
            return self
        return self.filter(scheduled_at__date=day)


class Reservation(models.Model):
    client = models.ForeignKey(
        "clients.Client",
        verbose_name="clienta",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    scheduled_at = models.DateTimeField("fecha programada")
    status = models.CharField(
        "estado",
        max_length=20,
        choices=StatusChoices,
        default=StatusChoices.PENDING,
    )
    attended_at = models.DateTimeField("atendida el", null=True, blank=True)
    notes = models.TextField("observaciones", blank=True, default="")
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    objects = ReservationQuerySet.as_manager()

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["-scheduled_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=StatusChoices.values),
                name="reservation_status_valid",
            ),
        ]

    def __str__(self):
        if self.scheduled_at is None:
            return f"{self.client} — sin fecha"
        when = timezone.localtime(self.scheduled_at)
        return f"{self.client} — {formats.date_format(when, 'j/n/Y H:i')}"

    def save(self, *args, **kwargs):
        self.notes = (self.notes or "").strip()
        super().save(*args, **kwargs)

    def has_performed_services(self):
        """True si esta reserva ya originó una atención."""
        if self.pk is None:
            return False
        from performed_services.models import PerformedService

        return PerformedService.objects.filter(reservation_id=self.pk).exists()
