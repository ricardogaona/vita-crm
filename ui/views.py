from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_headers

from .forms import DemoForm


def _ensure_demo_enabled():
    if not settings.DEBUG:
        raise Http404


def _page_context(form, *, checked_at=None):
    return {
        "form": form,
        "saved": False,
        "saved_name": "",
        "checked_at": checked_at,
        "page_title": "Demostración",
        "page_description": "Referencia visual de layout, formularios y respuestas parciales.",
        "breadcrumbs": [
            {"label": "Vita CRM", "url": reverse("ui:demo")},
            {"label": "Demostración"},
        ],
        "rows": [
            {
                "name": "Ficha de ejemplo",
                "detail": "Registro ilustrativo. Esta pantalla no escribe en la base.",
            },
            {
                "name": "Otro ejemplo",
                "detail": "La tabla usa el marcado de Tabler y se adapta al ancho.",
            },
        ],
    }


@vary_on_headers("HX-Request")
@require_http_methods(["GET", "POST"])
def demo(request):
    _ensure_demo_enabled()
    form = DemoForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            saved_name = form.cleaned_data["name"]
            if request.htmx:
                return render(
                    request,
                    "pages/demo_form.html",
                    {"form": DemoForm(), "saved": True, "saved_name": saved_name},
                )
            messages.success(
                request,
                f"El formulario se validó correctamente para {saved_name}.",
            )
            return redirect("ui:demo")
        if request.htmx:
            return render(
                request,
                "pages/demo_form.html",
                {"form": form, "saved": False, "saved_name": ""},
            )

    return render(request, "pages/demo.html", _page_context(form))


@vary_on_headers("HX-Request")
@require_http_methods(["GET"])
def demo_status(request):
    _ensure_demo_enabled()
    checked_at = timezone.localtime()
    if request.htmx:
        return render(request, "pages/demo_status.html", {"checked_at": checked_at})
    return render(
        request,
        "pages/demo.html",
        _page_context(DemoForm(), checked_at=checked_at),
    )
