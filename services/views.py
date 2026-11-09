from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .models import CategoryChoices, Service

PAGE_SIZE = 25


def _page(title, description, breadcrumbs):
    if breadcrumbs:
        breadcrumbs[-1].pop("url", None)
    return {
        "page_title": title,
        "page_description": description,
        "breadcrumbs": breadcrumbs,
    }


@require_http_methods(["GET"])
def service_list(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("categoria", "").strip()
    if category not in CategoryChoices.values:
        category = ""
    status = request.GET.get("estado", "").strip()
    if status not in {"activos", "inactivos"}:
        status = ""
    services = Service.objects.search(query).by_category(category).by_status(status)
    page_obj = Paginator(services, PAGE_SIZE).get_page(request.GET.get("page"))
    context = _page(
        "Servicios",
        "Listado de servicios.",
        [{"label": "Servicios"}],
    )
    context.update(
        {
            "query": query,
            "categoria": category,
            "estado": status,
            "categories": CategoryChoices.choices,
            "page_obj": page_obj,
        }
    )
    return render(request, "services/list.html", context)


@require_http_methods(["GET"])
def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk)
    context = _page(
        str(service),
        "Datos del servicio.",
        [
            {"label": "Servicios", "url": reverse("servicios:lista")},
            {"label": str(service)},
        ],
    )
    context["service"] = service
    return render(request, "services/detail.html", context)
