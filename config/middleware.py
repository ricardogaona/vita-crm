from django.conf import settings
from django.contrib.auth.middleware import (
    LoginRequiredMiddleware as DjangoLoginRequiredMiddleware,
)
from django_htmx.http import HttpResponseClientRedirect


class LoginRequiredMiddleware(DjangoLoginRequiredMiddleware):
    """Exige sesión en cada vista y vuelve a la URL pedida tras el login del admin."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path in {"/health", "/health/"} or request.path.startswith(
            self._static_prefix()
        ):
            return None
        return super().process_view(request, view_func, view_args, view_kwargs)

    def handle_no_permission(self, request, view_func):
        redirect = super().handle_no_permission(request, view_func)
        if request.htmx:
            response = HttpResponseClientRedirect(redirect.url)
        else:
            response = redirect
        response.headers["Vary"] = "HX-Request"
        return response

    def _static_prefix(self):
        prefix = settings.STATIC_URL
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix
