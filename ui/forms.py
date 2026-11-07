from django import forms


class TablerFormMixin:
    """Aplica las clases y atributos de Tabler a los widgets del formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            self._style_field(name, field)

    def _style_field(self, name, field):
        widget = field.widget
        classes = [self._control_class(widget)]
        classes.extend(widget.attrs.get("class", "").split())

        bound = self[name]
        described_by = []
        if field.help_text:
            described_by.append(f"{bound.id_for_label}-help")
        if name in self.errors:
            classes.append("is-invalid")
            widget.attrs["aria-invalid"] = "true"
            described_by.append(f"{bound.id_for_label}-error")

        widget.attrs["class"] = " ".join(dict.fromkeys(item for item in classes if item))
        if described_by:
            widget.attrs["aria-describedby"] = " ".join(described_by)
        if field.required and getattr(widget, "input_type", "") not in {"checkbox", "radio"}:
            widget.attrs["required"] = True

    @staticmethod
    def _control_class(widget):
        if isinstance(widget, forms.Select):
            return "form-select"
        if getattr(widget, "input_type", "") in {"checkbox", "radio"}:
            return "form-check-input"
        return "form-control"


class TablerForm(TablerFormMixin, forms.Form):
    """Formulario suelto con el marcado de Tabler."""


class TablerModelForm(TablerFormMixin, forms.ModelForm):
    """Formulario de modelo con el marcado de Tabler."""


class DemoForm(TablerForm):
    name = forms.CharField(
        label="Nombre",
        min_length=2,
        max_length=80,
        help_text="Entre 2 y 80 caracteres.",
    )
    message = forms.CharField(
        label="Mensaje",
        min_length=10,
        max_length=280,
        help_text="Mínimo 10 caracteres. La validación la hace el servidor.",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
