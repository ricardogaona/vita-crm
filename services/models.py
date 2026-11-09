from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Upper


DUPLICATE_CODE = "Ya hay un servicio con este código."
REQUIRED_MESSAGES = {
    "code": "Indicá el código.",
    "name": "Indicá el nombre.",
}
DURATION_MESSAGE = "La duración tiene que ser de al menos un minuto."
PRICE_MESSAGE = "El precio no puede ser negativo."
COST_MESSAGE = "El costo estimado no puede ser negativo."


class CategoryChoices(models.TextChoices):
    GEL = "gel", "Gel"
    ACRYLIC = "acrylic", "Acrílico"
    SOFT_GEL = "soft_gel", "Soft Gel"
    REMOVAL = "removal", "Remoción"
    MANICURE_PEDICURE = "manicure_pedicure", "Manicura y pedicura"
    ADDITIONAL = "additional", "Adicionales"


class ServiceQuerySet(models.QuerySet):
    def search(self, query):
        text = (query or "").strip()
        if not text:
            return self
        results = self
        for term in text.split():
            results = results.filter(Q(code__icontains=term) | Q(name__icontains=term))
        return results

    def by_category(self, category):
        if category in CategoryChoices.values:
            return self.filter(category=category)
        return self

    def by_status(self, status):
        if status == "activos":
            return self.filter(is_active=True)
        if status == "inactivos":
            return self.filter(is_active=False)
        return self


class Service(models.Model):
    code = models.CharField("código", max_length=30, unique=True)
    name = models.CharField("nombre", max_length=150)
    category = models.CharField(
        "categoría",
        max_length=30,
        choices=CategoryChoices,
        blank=True,
        default="",
    )
    price_gs = models.PositiveBigIntegerField(
        "precio",
        validators=[MinValueValidator(0, PRICE_MESSAGE)],
        help_text="Precio de lista en guaraníes. No es necesariamente el monto cobrado.",
    )
    estimated_cost_gs = models.PositiveBigIntegerField(
        "costo estimado",
        null=True,
        blank=True,
        validators=[MinValueValidator(0, COST_MESSAGE)],
        help_text=(
            "Materiales e insumos, sin remuneración. "
            "Vacío si todavía no se conoce; 0 si el costo estimado es cero."
        ),
    )
    duration_minutes = models.PositiveIntegerField(
        "duración",
        null=True,
        blank=True,
        validators=[MinValueValidator(1, DURATION_MESSAGE)],
        help_text="Vacío si todavía no se conoce. Si se indica, al menos un minuto.",
    )
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    objects = ServiceQuerySet.as_manager()

    class Meta:
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        ordering = ["code", "pk"]
        constraints = [
            models.UniqueConstraint(
                Upper("code"),
                name="service_code_normalized_unique",
                violation_error_message=DUPLICATE_CODE,
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes__isnull=True) | Q(duration_minutes__gte=1),
                name="service_duration_at_least_one",
                violation_error_message=DURATION_MESSAGE,
            ),
            models.CheckConstraint(
                condition=Q(price_gs__gte=0),
                name="service_price_non_negative",
                violation_error_message=PRICE_MESSAGE,
            ),
            models.CheckConstraint(
                condition=Q(estimated_cost_gs__isnull=True) | Q(estimated_cost_gs__gte=0),
                name="service_estimated_cost_non_negative",
                violation_error_message=COST_MESSAGE,
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean_fields(self, exclude=None):
        self._normalize_text()
        excluded = set(exclude or [])
        errors = {}
        for field, message in REQUIRED_MESSAGES.items():
            if field not in excluded and not getattr(self, field):
                errors[field] = [message]
                excluded.add(field)
        try:
            super().clean_fields(exclude=excluded)
        except ValidationError as exc:
            exc.update_error_dict(errors)
        if errors:
            raise ValidationError(errors)

    def clean(self):
        super().clean()
        if not self.code:
            return
        duplicates = Service.objects.filter(code__iexact=self.code)
        if self.pk:
            duplicates = duplicates.exclude(pk=self.pk)
        if duplicates.exists():
            raise ValidationError({"code": DUPLICATE_CODE})

    def validate_unique(self, exclude=None):
        # El código se valida en clean() con la clave en mayúsculas.
        excluded = set(exclude or [])
        excluded.add("code")
        super().validate_unique(exclude=excluded)

    def validate_constraints(self, exclude=None):
        # Esa regla ya informa el campo en clean(). La base igual la impone.
        errors = {}
        for model_class, constraints in self.get_constraints():
            for constraint in constraints:
                if constraint.name == "service_code_normalized_unique":
                    continue
                try:
                    constraint.validate(model_class, self, exclude=exclude)
                except ValidationError as exc:
                    exc.update_error_dict(errors)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self._normalize_text()
        super().save(*args, **kwargs)

    def has_performed_services(self):
        """True si el servicio quedó en alguna atención."""
        if self.pk is None:
            return False
        items = getattr(self, "performed_service_items", None)
        if items is None:
            return False
        return items.exists()

    def _normalize_text(self):
        self.code = (self.code or "").strip().upper()
        self.name = (self.name or "").strip()
