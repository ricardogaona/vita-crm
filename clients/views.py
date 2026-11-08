from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ClientForm
from .models import Client

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
def client_list(request):
    query = request.GET.get("q", "").strip()
    clients = Client.objects.search(query)
    page_obj = Paginator(clients, PAGE_SIZE).get_page(request.GET.get("page"))
    context = _page(
        "Clientas",
        "Listado de clientas.",
        [{"label": "Clientas"}],
    )
    context.update({"query": query, "page_obj": page_obj})
    return render(request, "clients/list.html", context)


@require_http_methods(["GET", "POST"])
def client_create(request):
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        messages.success(request, f"Se registró a {client}.")
        return redirect("clientes:detalle", pk=client.pk)
    context = _page(
        "Nueva clienta",
        "Nombre y apellido alcanzan para el alta.",
        [
            {"label": "Clientas", "url": reverse("clientes:lista")},
            {"label": "Nueva"},
        ],
    )
    context.update({"form": form, "cancel_url": reverse("clientes:lista")})
    return render(request, "clients/form.html", context)


@require_http_methods(["GET"])
def client_detail(request, pk):
    client = get_object_or_404(Client.objects.select_related("referred_by"), pk=pk)
    context = _page(
        str(client),
        "Datos de la clienta.",
        [
            {"label": "Clientas", "url": reverse("clientes:lista")},
            {"label": str(client)},
        ],
    )
    context["client"] = client
    return render(request, "clients/detail.html", context)


@require_http_methods(["GET", "POST"])
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    form = ClientForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        messages.success(request, f"Se actualizaron los datos de {client}.")
        return redirect("clientes:detalle", pk=client.pk)
    context = _page(
        f"Editar {client}",
        "Los cambios quedan en la ficha. Desmarcar Activa no borra el historial.",
        [
            {"label": "Clientas", "url": reverse("clientes:lista")},
            {
                "label": str(client),
                "url": reverse("clientes:detalle", kwargs={"pk": client.pk}),
            },
            {"label": "Editar"},
        ],
    )
    context.update(
        {
            "form": form,
            "client": client,
            "cancel_url": reverse("clientes:detalle", kwargs={"pk": client.pk}),
        }
    )
    return render(request, "clients/form.html", context)


@require_POST
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if client.has_service_history():
        messages.error(
            request,
            "No se puede eliminar esta clienta porque tiene reservas o atenciones. "
            "Podés desactivarla.",
        )
        return redirect("clientes:detalle", pk=client.pk)
    name = str(client)
    client.delete()
    messages.success(request, f"Se eliminó a {name}.")
    return redirect("clientes:lista")
