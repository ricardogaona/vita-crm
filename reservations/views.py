from datetime import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.vary import vary_on_headers

from clients.forms import ClientForm
from clients.models import Client

from .forms import ReservationForm
from .models import Reservation, StatusChoices

PAGE_SIZE = 25
SEARCH_LIMIT = 20


def _page(title, description, breadcrumbs):
    if breadcrumbs:
        breadcrumbs[-1].pop("url", None)
    return {
        "page_title": title,
        "page_description": description,
        "breadcrumbs": breadcrumbs,
    }


def _selected_client(form):
    value = form["client"].value()
    if not value:
        return None, ""
    client = Client.objects.filter(pk=value).first()
    return client, value


def _parse_date(raw):
    text = (raw or "").strip()
    if not text:
        return None, ""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date(), text
    except ValueError:
        return None, ""


def _performed_service(reservation):
    from performed_services.models import PerformedService

    return (
        PerformedService.objects.filter(reservation=reservation)
        .select_related("client")
        .first()
    )


@require_GET
def reservation_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("estado", "").strip()
    if status not in StatusChoices.values:
        status = ""
    scheduled_on, fecha = _parse_date(request.GET.get("fecha", ""))
    reservations = (
        Reservation.objects.select_related("client")
        .for_client_search(query)
        .by_status(status)
        .on_date(scheduled_on)
    )
    page_obj = Paginator(reservations, PAGE_SIZE).get_page(request.GET.get("page"))
    context = _page(
        "Reservas",
        "Listado de reservas.",
        [{"label": "Reservas"}],
    )
    context.update(
        {
            "query": query,
            "estado": status,
            "fecha": fecha,
            "status_choices": StatusChoices.choices,
            "page_obj": page_obj,
        }
    )
    return render(request, "reservations/list.html", context)


@require_http_methods(["GET", "POST"])
def reservation_create(request):
    form = ReservationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reservation = form.save()
        messages.success(request, f"Se registró la reserva de {reservation.client}.")
        return redirect("reservas:detalle", pk=reservation.pk)
    selected, client_value = _selected_client(form)
    context = _page(
        "Nueva reserva",
        "Elegí la clienta, la fecha y el estado.",
        [
            {"label": "Reservas", "url": reverse("reservas:lista")},
            {"label": "Nueva"},
        ],
    )
    context.update(
        {
            "form": form,
            "selected_client": selected,
            "client_value": client_value,
            "cancel_url": reverse("reservas:lista"),
        }
    )
    return render(request, "reservations/form.html", context)


@require_GET
def reservation_detail(request, pk):
    reservation = get_object_or_404(
        Reservation.objects.select_related("client"),
        pk=pk,
    )
    context = _page(
        str(reservation),
        "Datos de la reserva.",
        [
            {"label": "Reservas", "url": reverse("reservas:lista")},
            {"label": str(reservation)},
        ],
    )
    context.update(
        {
            "reservation": reservation,
            "performed_service": _performed_service(reservation),
        }
    )
    return render(request, "reservations/detail.html", context)


@require_http_methods(["GET", "POST"])
def reservation_edit(request, pk):
    reservation = get_object_or_404(Reservation.objects.select_related("client"), pk=pk)
    form = ReservationForm(request.POST or None, instance=reservation)
    if request.method == "POST" and form.is_valid():
        reservation = form.save()
        messages.success(request, f"Se actualizó la reserva de {reservation.client}.")
        return redirect("reservas:detalle", pk=reservation.pk)
    selected, client_value = _selected_client(form)
    context = _page(
        f"Editar {reservation}",
        "Los cambios quedan en la reserva.",
        [
            {"label": "Reservas", "url": reverse("reservas:lista")},
            {
                "label": str(reservation),
                "url": reverse("reservas:detalle", kwargs={"pk": reservation.pk}),
            },
            {"label": "Editar"},
        ],
    )
    context.update(
        {
            "form": form,
            "reservation": reservation,
            "selected_client": selected,
            "client_value": client_value,
            "cancel_url": reverse("reservas:detalle", kwargs={"pk": reservation.pk}),
        }
    )
    return render(request, "reservations/form.html", context)


@require_POST
def reservation_delete(request, pk):
    reservation = get_object_or_404(Reservation.objects.select_related("client"), pk=pk)
    if reservation.has_performed_services():
        messages.error(
            request,
            "No se puede eliminar esta reserva porque tiene servicios realizados.",
        )
        return redirect("reservas:detalle", pk=reservation.pk)
    name = str(reservation.client)
    reservation.delete()
    messages.success(request, f"Se eliminó la reserva de {name}.")
    return redirect("reservas:lista")


@vary_on_headers("HX-Request")
@require_GET
def client_search(request):
    query = request.GET.get("q", "").strip()
    clients = Client.objects.none()
    if query:
        clients = Client.objects.search(query)[:SEARCH_LIMIT]
    return render(
        request,
        "reservations/partials/client_results.html",
        {"clients": clients, "query": query},
    )


@vary_on_headers("HX-Request")
@require_GET
def client_select(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(
        request,
        "reservations/partials/client_picker.html",
        {"selected_client": client, "client_value": client.pk},
    )


@vary_on_headers("HX-Request")
@require_http_methods(["GET", "POST"])
def client_create_modal(request):
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        response = render(
            request,
            "reservations/partials/client_created.html",
            {"selected_client": client},
        )
        response["HX-Trigger"] = "closeNewClientModal"
        return response
    return render(
        request,
        "reservations/partials/client_modal_form.html",
        {"form": form},
    )
