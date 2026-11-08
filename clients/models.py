from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class SourceChoices(models.TextChoices):
    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"
    TIKTOK = "tiktok", "TikTok"
    WHATSAPP = "whatsapp", "WhatsApp"
    GOOGLE_MAPS = "google_maps", "Google Maps"
    REFERRAL = "referido", "Referido"
    WALK_IN = "paso_por_el_local", "Paso por el local"
    LOCAL_PARTNERSHIP = "alianza_local", "Alianza local"
    OTHER = "otro", "Otro"


class ClientQuerySet(models.QuerySet):
    def search(self, query):
        text = (query or "").strip()
        if not text:
            return self
        results = self
        for term in text.split():
            results = results.filter(
                Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(identification_number__icontains=term)
                | Q(phone__icontains=term)
                | Q(email__icontains=term)
            )
        return results


class Client(models.Model):
    first_name = models.CharField("nombre", max_length=100)
    last_name = models.CharField("apellido", max_length=100)
    identification_number = models.CharField(
        "documento",
        max_length=30,
        blank=True,
        default="",
    )
    tax_id = models.CharField("RUC", max_length=30, blank=True, default="")
    tax_name = models.CharField("razón social", max_length=200, blank=True, default="")
    phone = models.CharField("teléfono", max_length=30, blank=True, default="")
    email = models.EmailField("correo electrónico", max_length=254, blank=True, default="")
    source = models.CharField(
        "origen",
        max_length=30,
        choices=SourceChoices,
        blank=True,
        default="",
    )
    referred_by = models.ForeignKey(
        "self",
        verbose_name="referida por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referred_clients",
    )
    first_contact_date = models.DateField("primer contacto", null=True, blank=True)
    marketing_consent = models.BooleanField(
        "consentimiento de marketing",
        default=False,
        help_text="Solo si aceptó recibir comunicaciones promocionales.",
    )
    marketing_consent_at = models.DateTimeField(
        "fecha del consentimiento",
        null=True,
        blank=True,
    )
    notes = models.TextField("notas", blank=True, default="")
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    objects = ClientQuerySet.as_manager()

    class Meta:
        verbose_name = "clienta"
        verbose_name_plural = "clientas"
        ordering = ["last_name", "first_name", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(referred_by__isnull=True) | ~Q(referred_by=F("pk")),
                name="client_not_self_referred",
            ),
        ]

    def __str__(self):
        return f"{self.last_name}, {self.first_name}"

    def clean(self):
        super().clean()
        self.first_name = (self.first_name or "").strip()
        self.last_name = (self.last_name or "").strip()
        errors = {}
        if not self.first_name:
            errors["first_name"] = "Indicá el nombre."
        if not self.last_name:
            errors["last_name"] = "Indicá el apellido."
        if self.pk and self.referred_by_id == self.pk:
            errors["referred_by"] = "Una clienta no puede estar referida por sí misma."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.first_name = (self.first_name or "").strip()
        self.last_name = (self.last_name or "").strip()
        if self.marketing_consent and self.marketing_consent_at is None:
            self.marketing_consent_at = timezone.now()
        super().save(*args, **kwargs)

    def has_service_history(self):
        """True si la clienta tiene reservas o atenciones. Eso impide eliminarla."""
        if self.pk is None:
            return False
        if self.reservations.exists():
            return True
        performed = getattr(self, "performed_services", None)
        if performed is None:
            return False
        return performed.exists()
