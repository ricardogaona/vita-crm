from django import template

register = template.Library()


@register.filter
def guaranies(value):
    if value is None or value == "":
        return "—"
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return value
    return f"Gs. {amount:,}".replace(",", ".")


@register.filter
def mul(value, other):
    try:
        return int(value) * int(other)
    except (TypeError, ValueError):
        return 0
