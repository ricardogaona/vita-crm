from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q, Value
from django.db.models.functions import Lower, Replace

IDENTIFICATION_SEPARATORS = (" ", ".", "-")

REQUIRED_MESSAGES = {
    "first_name": "Indicá el nombre.",
    "last_name": "Indicá el apellido.",
    "identification_number": "Indicá el documento.",
    "phone": "Indicá el teléfono.",
    "email": "Indicá el correo electrónico.",
}

DUPLICATE_DOCUMENT = "Ya hay una profesional con este documento."
END_BEFORE_START = "La fecha de finalización no puede ser anterior a la de incorporación."


def identification_key(value):
    """Clave de unicidad: minúsculas, sin espacios, puntos ni guiones."""
    text = (value or "").strip().lower()
    for character in IDENTIFICATION_SEPARATORS:
        text = text.replace(character, "")
    return text


def identification_key_expression():
    expression = F("identification_number")
    for character in IDENTIFICATION_SEPARATORS:
        expression = Replace(expression, Value(character), Value(""))
    return Lower(expression)


class ProfessionalQuerySet(models.QuerySet):
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

    def by_status(self, status):
        if status == "activas":
            return self.filter(is_active=True)
        if status == "inactivas":
            return self.filter(is_active=False)
        return self


class Professional(models.Model):
    first_name = models.CharField("nombre", max_length=100)
    last_name = models.CharField("apellido", max_length=100)
    identification_number = models.CharField("documento", max_length=30, unique=True)
    phone = models.CharField("teléfono", max_length=30)
    email = models.EmailField("correo electrónico", max_length=254)
    is_active = models.BooleanField("activa", default=True)
    start_date = models.DateField("incorporación", null=True, blank=True)
    end_date = models.DateField("finalización", null=True, blank=True)
    notes = models.TextField("notas", blank=True, default="")
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    objects = ProfessionalQuerySet.as_manager()

    class Meta:
        verbose_name = "profesional"
        verbose_name_plural = "profesionales"
        ordering = ["last_name", "first_name", "pk"]
        constraints = [
            models.UniqueConstraint(
                identification_key_expression(),
                name="professional_identification_normalized_unique",
                violation_error_message=DUPLICATE_DOCUMENT,
            ),
            models.CheckConstraint(
                condition=(
                    Q(end_date__isnull=True)
                    | Q(start_date__isnull=True)
                    | Q(end_date__gte=F("start_date"))
                ),
                name="professional_end_on_or_after_start",
                violation_error_message=END_BEFORE_START,
            ),
        ]

    def __str__(self):
        return f"{self.last_name}, {self.first_name}"

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
        errors = {}
        key = identification_key(self.identification_number)
        if key:
            duplicates = Professional.objects.alias(
                identification_key=identification_key_expression()
            ).filter(identification_key=key)
            if self.pk:
                duplicates = duplicates.exclude(pk=self.pk)
            if duplicates.exists():
                errors["identification_number"] = DUPLICATE_DOCUMENT
        elif self.identification_number:
            errors["identification_number"] = REQUIRED_MESSAGES["identification_number"]
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = END_BEFORE_START
        if errors:
            raise ValidationError(errors)

    def validate_unique(self, exclude=None):
        # El documento se valida en clean() con la clave normalizada.
        excluded = set(exclude or [])
        excluded.add("identification_number")
        super().validate_unique(exclude=excluded)

    def validate_constraints(self, exclude=None):
        # Esas reglas ya informan el campo en clean(). La base igual las impone.
        errors = {}
        skipped = {
            "professional_identification_normalized_unique",
            "professional_end_on_or_after_start",
        }
        for model_class, constraints in self.get_constraints():
            for constraint in constraints:
                if constraint.name in skipped:
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

    def has_service_history(self):
        """Servicios realizados. La relación llega con PerformedService."""
        if self.pk is None:
            return False
        performed_services = getattr(self, "performed_services", None)
        if performed_services is None:
            return False
        return performed_services.exists()

    def _normalize_text(self):
        self.first_name = (self.first_name or "").strip()
        self.last_name = (self.last_name or "").strip()
        self.identification_number = (self.identification_number or "").strip()
        self.phone = (self.phone or "").strip()
        self.email = (self.email or "").strip()
        self.notes = (self.notes or "").strip()
