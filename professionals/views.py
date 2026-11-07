from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ProfessionalForm
from .models import Professional

PAGE_SIZE = 25


def _page(title, description, breadcrumbs):
    if breadcrumbs:
        breadcrumbs[-1].pop("url", None)
    return {
        "page_title": title,
        "page_description": description,
        "breadcrumbs": breadcrumbs,
    }


def _service_history(professional):
    performed_services = getattr(professional, "performed_services", None)
    if performed_services is None:
        return None
    rows = []
    for service in performed_services.all():
        reservation = getattr(service, "reservation", None)
        client = getattr(reservation, "client", None) if reservation is not None else None
        performed_on = None
        for name in ("performed_on", "performed_at", "date", "service_date"):
            performed_on = getattr(service, name, None)
            if performed_on:
                break
        rows.append(
            {
                "performed_on": performed_on,
                "reservation": reservation,
                "client": client,
            }
        )
    return rows


@require_http_methods(["GET"])
def professional_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("estado", "").strip()
    if status not in {"activas", "inactivas"}:
        status = ""
    professionals = Professional.objects.search(query).by_status(status)
    page_obj = Paginator(professionals, PAGE_SIZE).get_page(request.GET.get("page"))
    context = _page(
        "Profesionales",
        "Listado de profesionales.",
        [{"label": "Profesionales"}],
    )
    context.update(
        {
            "query": query,
            "estado": status,
            "page_obj": page_obj,
        }
    )
    return render(request, "professionals/list.html", context)


@require_http_methods(["GET", "POST"])
def professional_create(request):
    form = ProfessionalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        professional = form.save()
        messages.success(request, f"Se registró a {professional}.")
        return redirect("profesionales:detalle", pk=professional.pk)
    context = _page(
        "Nueva profesional",
        "Nombre, apellido, documento, teléfono y correo son obligatorios.",
        [
            {"label": "Profesionales", "url": reverse("profesionales:lista")},
            {"label": "Nueva"},
        ],
    )
    context.update({"form": form, "cancel_url": reverse("profesionales:lista")})
    return render(request, "professionals/form.html", context)


@require_http_methods(["GET"])
def professional_detail(request, pk):
    professional = get_object_or_404(Professional, pk=pk)
    context = _page(
        str(professional),
        "Datos de la profesional.",
        [
            {"label": "Profesionales", "url": reverse("profesionales:lista")},
            {"label": str(professional)},
        ],
    )
    context.update(
        {
            "professional": professional,
            "service_history": _service_history(professional),
        }
    )
    return render(request, "professionals/detail.html", context)


@require_http_methods(["GET", "POST"])
def professional_edit(request, pk):
    professional = get_object_or_404(Professional, pk=pk)
    form = ProfessionalForm(request.POST or None, instance=professional)
    if request.method == "POST" and form.is_valid():
        professional = form.save()
        messages.success(request, f"Se actualizaron los datos de {professional}.")
        return redirect("profesionales:detalle", pk=professional.pk)
    context = _page(
        f"Editar {professional}",
        "Los cambios quedan en la ficha. Desmarcar Activa no borra el historial.",
        [
            {"label": "Profesionales", "url": reverse("profesionales:lista")},
            {
                "label": str(professional),
                "url": reverse("profesionales:detalle", kwargs={"pk": professional.pk}),
            },
            {"label": "Editar"},
        ],
    )
    context.update(
        {
            "form": form,
            "professional": professional,
            "cancel_url": reverse("profesionales:detalle", kwargs={"pk": professional.pk}),
        }
    )
    return render(request, "professionals/form.html", context)


@require_POST
def professional_deactivate(request, pk):
    professional = get_object_or_404(Professional, pk=pk)
    professional.is_active = False
    professional.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"Se desactivó a {professional}. El historial se conserva.")
    return redirect("profesionales:detalle", pk=professional.pk)


@require_POST
def professional_delete(request, pk):
    professional = get_object_or_404(Professional, pk=pk)
    if professional.has_service_history():
        messages.error(
            request,
            "No se puede eliminar esta profesional porque tiene historial de servicios. "
            "Podés desactivarla.",
        )
        return redirect("profesionales:detalle", pk=professional.pk)
    name = str(professional)
    professional.delete()
    messages.success(request, f"Se eliminó a {name}.")
    return redirect("profesionales:lista")
