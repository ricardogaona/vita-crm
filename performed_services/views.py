import re
from datetime import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.vary import vary_on_headers

from clients.models import Client
from professionals.models import Professional
from reservations.models import Reservation
from services.models import Service

from .forms import PerformedServiceForm, PerformedServiceItemForm, build_item_formset
from .models import PerformedService

PAGE_SIZE = 25
SEARCH_LIMIT = 20
PREFIX_RE = re.compile(r"items-\d+")


def _page(title, description, breadcrumbs):
    if breadcrumbs:
        breadcrumbs[-1].pop("url", None)
    return {
        "page_title": title,
        "page_description": description,
        "breadcrumbs": breadcrumbs,
    }


def _parse_date(raw):
    text = (raw or "").strip()
    if not text:
        return None, ""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date(), text
    except ValueError:
        return None, ""


def _flag(value):
    return value in (True, "on", "true", "True", "1")


def _has_reservation(form):
    return _flag(form["has_reservation"].value())


def _selected_client(form):
    value = form["client"].value()
    if not value:
        return None, ""
    client = Client.objects.filter(pk=value).first()
    return client, value


def _selected_reservation(form):
    value = form["reservation"].value()
    if not value:
        return None, ""
    reservation = Reservation.objects.select_related("client").filter(pk=value).first()
    return reservation, value


def _include_pk(raw):
    text = (raw or "").strip()
    if text.isdigit():
        return int(text)
    return None


def _available_reservations(include_pk=None):
    query = Q(performed_service__isnull=True)
    if include_pk:
        query |= Q(pk=include_pk)
    return Reservation.objects.filter(query).select_related("client")


def _preview(form, formset):
    services_total = 0
    for item_form in formset.forms:
        if _flag(item_form["DELETE"].value()):
            continue
        try:
            price = int(item_form["unit_price_gs"].value() or 0)
            quantity = int(item_form["quantity"].value() or 0)
        except (TypeError, ValueError):
            continue
        if quantity < 0 or price < 0:
            continue
        services_total += price * quantity
    try:
        charge = int(form["additional_charge_gs"].value() or 0)
    except (TypeError, ValueError):
        charge = 0
    if charge < 0:
        charge = 0
    return services_total, services_total + charge


def _form_context(form, formset, cancel_url, current_reservation_id=None):
    selected_client, client_value = _selected_client(form)
    selected_reservation, reservation_value = _selected_reservation(form)
    services_subtotal, grand_total = _preview(form, formset)
    return {
        "form": form,
        "formset": formset,
        "cancel_url": cancel_url,
        "has_reservation": _has_reservation(form),
        "selected_client": selected_client,
        "client_value": client_value,
        "selected_reservation": selected_reservation,
        "reservation_value": reservation_value,
        "current_reservation_id": current_reservation_id,
        "services_subtotal": services_subtotal,
        "grand_total": grand_total,
    }


def _save_attention(form, formset):
    with transaction.atomic():
        attention = form.save(commit=False)
        attention.save()
        formset.instance = attention
        formset.save()
        attention.recalculate_total()
        attention.save(update_fields=["total_price_gs", "updated_at"])
        return attention


@require_GET
def performed_service_list(request):
    query = request.GET.get("q", "").strip()
    professional_id = request.GET.get("profesional", "").strip()
    if not professional_id.isdigit():
        professional_id = ""
    start, desde = _parse_date(request.GET.get("desde", ""))
    end, hasta = _parse_date(request.GET.get("hasta", ""))
    attentions = (
        PerformedService.objects.select_related("client", "professional")
        .annotate(item_count=Count("items"))
        .for_client_search(query)
        .for_professional(professional_id)
        .between(start, end)
        .order_by("-performed_at", "-pk")
    )
    page_obj = Paginator(attentions, PAGE_SIZE).get_page(request.GET.get("page"))
    context = _page(
        "Atenciones",
        "Listado de atenciones.",
        [{"label": "Atenciones"}],
    )
    context.update(
        {
            "query": query,
            "profesional": professional_id,
            "desde": desde,
            "hasta": hasta,
            "professionals": Professional.objects.all(),
            "page_obj": page_obj,
        }
    )
    return render(request, "performed_services/list.html", context)


@require_http_methods(["GET", "POST"])
def performed_service_create(request):
    attention = PerformedService()
    form = PerformedServiceForm(request.POST or None, instance=attention)
    formset = build_item_formset(request.POST or None, instance=attention)
    if request.method == "POST":
        form_valid = form.is_valid()
        formset_valid = formset.is_valid()
        if form_valid and formset_valid:
            attention = _save_attention(form, formset)
            messages.success(request, f"Se registró la atención de {attention.client}.")
            return redirect("atenciones:detalle", pk=attention.pk)
    context = _page(
        "Nueva atención",
        "Elegí la reserva o la clienta, la profesional y los servicios.",
        [
            {"label": "Atenciones", "url": reverse("atenciones:lista")},
            {"label": "Nueva"},
        ],
    )
    context.update(_form_context(form, formset, reverse("atenciones:lista")))
    return render(request, "performed_services/form.html", context)


@require_GET
def performed_service_detail(request, pk):
    attention = get_object_or_404(
        PerformedService.objects.select_related(
            "client",
            "professional",
            "reservation",
            "reservation__client",
        ).prefetch_related("items__service"),
        pk=pk,
    )
    context = _page(
        str(attention),
        "Datos de la atención.",
        [
            {"label": "Atenciones", "url": reverse("atenciones:lista")},
            {"label": str(attention)},
        ],
    )
    context["attention"] = attention
    return render(request, "performed_services/detail.html", context)


@require_http_methods(["GET", "POST"])
def performed_service_edit(request, pk):
    attention = get_object_or_404(
        PerformedService.objects.select_related("client", "reservation", "professional"),
        pk=pk,
    )
    form = PerformedServiceForm(request.POST or None, instance=attention)
    formset = build_item_formset(request.POST or None, instance=attention)
    if request.method == "POST":
        form_valid = form.is_valid()
        formset_valid = formset.is_valid()
        if form_valid and formset_valid:
            attention = _save_attention(form, formset)
            messages.success(request, f"Se actualizó la atención de {attention.client}.")
            return redirect("atenciones:detalle", pk=attention.pk)
    context = _page(
        f"Editar {attention}",
        "Los cambios quedan en la atención y en sus servicios.",
        [
            {"label": "Atenciones", "url": reverse("atenciones:lista")},
            {
                "label": str(attention),
                "url": reverse("atenciones:detalle", kwargs={"pk": attention.pk}),
            },
            {"label": "Editar"},
        ],
    )
    context.update(
        _form_context(
            form,
            formset,
            reverse("atenciones:detalle", kwargs={"pk": attention.pk}),
            current_reservation_id=attention.reservation_id,
        )
    )
    context["attention"] = attention
    return render(request, "performed_services/form.html", context)


@require_POST
def performed_service_delete(request, pk):
    attention = get_object_or_404(
        PerformedService.objects.select_related("client"),
        pk=pk,
    )
    name = str(attention.client)
    attention.delete()
    messages.success(request, f"Se eliminó la atención de {name}.")
    return redirect("atenciones:lista")


@vary_on_headers("HX-Request")
@require_GET
def reservation_search(request):
    query = (request.GET.get("reserva_q") or request.GET.get("q") or "").strip()
    include_pk = _include_pk(request.GET.get("actual"))
    reservations = Reservation.objects.none()
    if query:
        available = _available_reservations(include_pk)
        matched = available.filter(client__in=Client.objects.search(query))
        if query.isdigit():
            matched = (matched | available.filter(pk=int(query))).distinct()
        reservations = matched.order_by("-scheduled_at", "-pk")[:SEARCH_LIMIT]
    return render(
        request,
        "performed_services/partials/reservation_results.html",
        {
            "reservations": reservations,
            "query": query,
            "current_reservation_id": include_pk,
        },
    )


@vary_on_headers("HX-Request")
@require_GET
def reservation_select(request, pk):
    include_pk = _include_pk(request.GET.get("actual"))
    reservation = get_object_or_404(_available_reservations(include_pk), pk=pk)
    return render(
        request,
        "performed_services/partials/reservation_picker.html",
        {
            "selected_reservation": reservation,
            "reservation_value": reservation.pk,
            "current_reservation_id": include_pk or reservation.pk,
        },
    )


@vary_on_headers("HX-Request")
@require_GET
def item_row(request):
    try:
        index = int(request.GET.get("index", ""))
    except ValueError:
        return HttpResponseBadRequest("Índice inválido.")
    if index < 0 or index > 29:
        return HttpResponseBadRequest("Índice inválido.")
    form = PerformedServiceItemForm(prefix=f"items-{index}")
    return render(
        request,
        "performed_services/partials/item_row.html",
        {"form": form, "next_total": index + 1},
    )


def _service_prefix(raw):
    prefix = raw or ""
    if not PREFIX_RE.fullmatch(prefix):
        return None
    return prefix


@vary_on_headers("HX-Request")
@require_GET
def service_search(request):
    prefix = _service_prefix(request.GET.get("prefix"))
    if prefix is None:
        return HttpResponseBadRequest("Prefijo inválido.")
    query = (request.GET.get("servicio_q") or "").strip()
    services = Service.objects.none()
    if query:
        services = (
            Service.objects.filter(is_active=True)
            .filter(Q(code__icontains=query) | Q(name__icontains=query))
            .order_by("code", "pk")[:SEARCH_LIMIT]
        )
    return render(
        request,
        "performed_services/partials/service_results.html",
        {"services": services, "query": query, "prefix": prefix},
    )


@vary_on_headers("HX-Request")
@require_GET
def service_select(request, pk):
    prefix = _service_prefix(request.GET.get("prefix"))
    if prefix is None:
        return HttpResponseBadRequest("Prefijo inválido.")
    service = get_object_or_404(Service, pk=pk, is_active=True)
    form = PerformedServiceItemForm(
        prefix=prefix,
        initial={"service": service.pk, "unit_price_gs": service.price_gs},
    )
    return render(
        request,
        "performed_services/partials/service_picker.html",
        {"form": form, "swap_price": True},
    )


@vary_on_headers("HX-Request")
@require_GET
def item_price(request):
    prefix = request.GET.get("prefix", "")
    if not PREFIX_RE.fullmatch(prefix):
        return HttpResponseBadRequest("Prefijo inválido.")
    service = Service.objects.filter(
        pk=request.GET.get(f"{prefix}-service"),
        is_active=True,
    ).first()
    form = PerformedServiceItemForm(
        prefix=prefix,
        initial={"unit_price_gs": service.price_gs if service else None},
    )
    return render(
        request,
        "performed_services/partials/unit_price.html",
        {"field": form["unit_price_gs"]},
    )
