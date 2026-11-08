from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.db.models import Count, Prefetch, Q, Sum
from django.db.models.functions import Coalesce, TruncDay, TruncMonth
from django.utils import timezone

from performed_services.models import PerformedService, PerformedServiceItem
from reservations.models import Reservation, StatusChoices


ASUNCION = ZoneInfo("America/Asuncion")

PERIOD_CHOICES = (
    ("hoy", "Hoy"),
    ("semana", "Esta semana"),
    ("mes", "Este mes"),
    ("mes_anterior", "Mes anterior"),
    ("ano", "Este año"),
    ("personalizado", "Personalizado"),
)
PERIOD_KEYS = {key for key, _label in PERIOD_CHOICES}
DEFAULT_PERIOD = "mes"

ERROR_MISSING = "Indicá desde y hasta."
ERROR_INVALID = "Las fechas no son válidas."
ERROR_RANGE = "La fecha hasta tiene que ser igual o posterior a desde."

MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
SHORT_MONTHS = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)

STATUS_COLORS = {
    StatusChoices.PENDING: "#f59f00",
    StatusChoices.CONFIRMED: "#206bc4",
    StatusChoices.ATTENDED: "#2fb344",
    StatusChoices.CANCELLED: "#d63939",
    StatusChoices.NO_SHOW: "#f76707",
}

DAILY_LIMIT = 31


class Period:
    def __init__(self, key, start, end, desde, hasta, error):
        self.key = key
        self.start = start
        self.end = end
        self.desde = desde
        self.hasta = hasta
        self.error = error


def midnight(day):
    return datetime(day.year, day.month, day.day, tzinfo=ASUNCION)


def inclusive_days(start, end):
    start_day = start.astimezone(ASUNCION).date()
    end_day = end.astimezone(ASUNCION).date()
    return (end_day - start_day).days


def uses_monthly(start, end):
    return inclusive_days(start, end) > DAILY_LIMIT


def _month_bounds(year, month):
    start = midnight(date(year, month, 1))
    if month == 12:
        end = midnight(date(year + 1, 1, 1))
    else:
        end = midnight(date(year, month + 1, 1))
    return start, end


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return "invalid"


def resolve_period(periodo, desde, hasta, *, today=None):
    key = (periodo or "").strip()
    if key not in PERIOD_KEYS:
        key = DEFAULT_PERIOD
    desde_text = (desde or "").strip()
    hasta_text = (hasta or "").strip()
    today = today or datetime.now(ASUNCION).date()

    if key == "personalizado":
        start_day = _parse_date(desde_text)
        end_day = _parse_date(hasta_text)
        if start_day is None or end_day is None:
            return Period(key, None, None, desde_text, hasta_text, ERROR_MISSING)
        if start_day == "invalid" or end_day == "invalid":
            return Period(key, None, None, desde_text, hasta_text, ERROR_INVALID)
        if end_day < start_day:
            return Period(key, None, None, desde_text, hasta_text, ERROR_RANGE)
        return Period(
            key,
            midnight(start_day),
            midnight(end_day + timedelta(days=1)),
            desde_text,
            hasta_text,
            "",
        )

    if key == "hoy":
        start, end = midnight(today), midnight(today + timedelta(days=1))
    elif key == "semana":
        monday = today - timedelta(days=today.weekday())
        start, end = midnight(monday), midnight(monday + timedelta(days=7))
    elif key == "mes_anterior":
        first = date(today.year, today.month, 1) - timedelta(days=1)
        start, end = _month_bounds(first.year, first.month)
    elif key == "ano":
        start, end = midnight(date(today.year, 1, 1)), midnight(date(today.year + 1, 1, 1))
    else:
        start, end = _month_bounds(today.year, today.month)
    return Period(key, start, end, desde_text, hasta_text, "")


def _performed(start, end):
    return PerformedService.objects.filter(performed_at__gte=start, performed_at__lt=end)


def average_ticket(total, count):
    if not count:
        return None
    amount = (Decimal(total) / Decimal(count)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(amount)


def attention_kpis(start, end):
    stats = _performed(start, end).aggregate(
        value=Coalesce(Sum("total_price_gs"), 0),
        count=Count("pk"),
        clients=Count("client_id", distinct=True),
    )
    value = int(stats["value"] or 0)
    count = stats["count"]
    return {
        "value": value,
        "count": count,
        "clients": stats["clients"],
        "ticket": average_ticket(value, count),
    }


def _bucket_date(value, monthly):
    if isinstance(value, datetime):
        current = timezone.localtime(value, ASUNCION).date()
    else:
        current = value
    if monthly:
        return current.replace(day=1)
    return current


def _iter_days(start, end):
    day = start.astimezone(ASUNCION).date()
    last = end.astimezone(ASUNCION).date()
    while day < last:
        yield day
        day += timedelta(days=1)


def _iter_months(start, end):
    current = start.astimezone(ASUNCION).date().replace(day=1)
    included_last = end.astimezone(ASUNCION).date() - timedelta(days=1)
    last = included_last.replace(day=1)
    while current <= last:
        yield current
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)


def _axis_label(day, monthly):
    if monthly:
        return f"{SHORT_MONTHS[day.month - 1]} {day.year}"
    return f"{day.day}/{day.month}"


def _full_label(day, monthly):
    if monthly:
        return f"{MONTHS[day.month - 1]} {day.year}"
    return f"{day.day}/{day.month}/{day.year}"


def evolution_chart(start, end):
    monthly = uses_monthly(start, end)
    trunc = TruncMonth if monthly else TruncDay
    rows = (
        _performed(start, end)
        .order_by()
        .annotate(bucket=trunc("performed_at", tzinfo=ASUNCION))
        .values("bucket")
        .annotate(total=Sum("total_price_gs"))
        .order_by("bucket")
    )
    totals = {}
    for row in rows:
        if row["bucket"] is None:
            continue
        totals[_bucket_date(row["bucket"], monthly)] = int(row["total"] or 0)
    if not totals:
        return None
    labels = []
    full_labels = []
    values = []
    for day in _iter_months(start, end) if monthly else _iter_days(start, end):
        labels.append(_axis_label(day, monthly))
        full_labels.append(_full_label(day, monthly))
        values.append(totals.get(day, 0))
    return {
        "labels": labels,
        "fullLabels": full_labels,
        "values": values,
        "monthly": monthly,
    }


def top_services(start, end):
    rows = list(
        PerformedServiceItem.objects.filter(
            performed_service__performed_at__gte=start,
            performed_service__performed_at__lt=end,
        )
        .order_by()
        .values("service_id", "service__name", "service__code")
        .annotate(units=Sum("quantity"))
        .order_by("-units", "service__name", "service__code")[:5]
    )
    if not rows:
        return None
    return {
        "labels": [row["service__name"] for row in rows],
        "values": [int(row["units"]) for row in rows],
    }


def _percent_label(part, total):
    value = (Decimal(part) * Decimal(100) / Decimal(total)).quantize(
        Decimal("0.1"),
        rounding=ROUND_HALF_UP,
    )
    return f"{value:.1f}".replace(".", ",")


def reservation_split(start, end):
    stats = _performed(start, end).aggregate(
        with_reservation=Count("pk", filter=Q(reservation_id__isnull=False)),
        without_reservation=Count("pk", filter=Q(reservation_id__isnull=True)),
    )
    with_reservation = stats["with_reservation"]
    without_reservation = stats["without_reservation"]
    total = with_reservation + without_reservation
    if total == 0:
        return None
    return {
        "labels": ["Con reserva", "Sin reserva"],
        "values": [with_reservation, without_reservation],
        "percents": [
            _percent_label(with_reservation, total),
            _percent_label(without_reservation, total),
        ],
    }


def reservation_statuses(start, end):
    rows = (
        Reservation.objects.filter(scheduled_at__gte=start, scheduled_at__lt=end)
        .order_by()
        .values("status")
        .annotate(total=Count("pk"))
    )
    counts = {row["status"]: row["total"] for row in rows}
    if not any(counts.values()):
        return None
    return {
        "labels": [choice.label for choice in StatusChoices],
        "values": [counts.get(choice.value, 0) for choice in StatusChoices],
        "colors": [STATUS_COLORS[choice] for choice in StatusChoices],
    }


def service_summary(attention):
    parts = []
    for item in attention.items.all():
        name = item.service.name
        if item.quantity > 1:
            parts.append(f"{name} × {item.quantity}")
        else:
            parts.append(name)
    return ", ".join(parts) if parts else "—"


def recent_attentions(start, end):
    attentions = list(
        _performed(start, end)
        .select_related("client", "professional")
        .prefetch_related(
            Prefetch(
                "items",
                queryset=PerformedServiceItem.objects.select_related("service"),
            )
        )
        .order_by("-performed_at", "-pk")[:10]
    )
    for attention in attentions:
        attention.service_summary = service_summary(attention)
    return attentions


def chart_payload(start, end):
    return {
        "evolution": evolution_chart(start, end),
        "services": top_services(start, end),
        "split": reservation_split(start, end),
        "statuses": reservation_statuses(start, end),
    }
