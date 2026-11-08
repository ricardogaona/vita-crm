from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .queries import (
    ASUNCION,
    PERIOD_CHOICES,
    attention_kpis,
    chart_payload,
    recent_attentions,
    resolve_period,
)


@require_GET
def dashboard(request):
    with timezone.override(ASUNCION):
        period = resolve_period(
            request.GET.get("periodo", ""),
            request.GET.get("desde", ""),
            request.GET.get("hasta", ""),
        )
        context = {
            "page_title": "Dashboard",
            "page_description": "Resumen de actividad del spa",
            "breadcrumbs": [{"label": "Dashboard"}],
            "period_choices": PERIOD_CHOICES,
            "periodo": period.key,
            "desde": period.desde,
            "hasta": period.hasta,
            "period_error": period.error,
            "kpis": None,
            "charts": None,
            "recent": [],
        }
        if not period.error:
            context["kpis"] = attention_kpis(period.start, period.end)
            context["charts"] = chart_payload(period.start, period.end)
            context["recent"] = recent_attentions(period.start, period.end)
        return render(request, "dashboard/index.html", context)
