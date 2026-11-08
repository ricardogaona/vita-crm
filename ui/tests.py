from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from config.middleware import LoginRequiredMiddleware

User = get_user_model()


def login_url_for(path):
    return f"{reverse('admin:login')}?next={path}"


@override_settings(DEBUG=True)
class DashboardShellTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("visitante", password="clave-segura")
        self.client.force_login(self.user)

    def test_get_returns_full_page(self):
        response = self.client.get(reverse("inicio"))

        self.assertContains(response, "<!DOCTYPE html>")
        self.assertContains(response, 'lang="es"')
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "tabler.min.css")
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "hx-headers")
        self.assertContains(response, "x-csrftoken")
        self.assertNotContains(response, "Demostración")

    def test_assets_are_local_and_htmx_loads_once(self):
        response = self.client.get(reverse("inicio"))
        html = response.content.decode()

        self.assertEqual(html.count("htmx-2.min.js"), 1)
        self.assertEqual(html.count("tabler.min.css"), 1)
        self.assertEqual(html.count("tabler.min.js"), 1)
        self.assertEqual(html.count("tabler-icons.min.css"), 1)
        self.assertIn("django-htmx.js", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertNotIn("unpkg.com", html)
        self.assertNotIn("bootstrap.min.css", html)
        self.assertNotIn("bootstrap.min.js", html)


class LoginRequiredTests(TestCase):
    def test_anonymous_health_is_public(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_anonymous_dashboard_redirects_to_admin_login(self):
        path = reverse("inicio")
        response = self.client.get(path)

        self.assertRedirects(response, login_url_for(path))
        self.assertIn("HX-Request", response.headers["Vary"])

    def test_anonymous_admin_index_redirects_to_admin_login(self):
        path = reverse("admin:index")
        response = self.client.get(path)

        self.assertRedirects(response, login_url_for(path))

    def test_anonymous_htmx_redirects_without_layout(self):
        path = reverse("inicio")
        response = self.client.get(path, HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["HX-Redirect"], login_url_for(path))
        self.assertIn("HX-Request", response.headers["Vary"])
        self.assertNotIn("tabler.min.css", response.content.decode())
        self.assertNotIn("<!DOCTYPE html>", response.content.decode())

    def test_anonymous_post_redirects_before_method_check(self):
        path = reverse("inicio")
        response = self.client.post(path)

        self.assertRedirects(response, login_url_for(path))

    def test_admin_login_is_public(self):
        response = self.client.get(reverse("admin:login"))

        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_staff_login_returns_to_requested_page(self):
        User.objects.create_user("ana", password="clave-segura", is_staff=True)
        next_url = reverse("inicio")
        response = self.client.post(
            reverse("admin:login"),
            {"username": "ana", "password": "clave-segura", "next": next_url},
        )

        self.assertRedirects(response, next_url)

    def test_static_requests_skip_login(self):
        request = RequestFactory().get("/static/css/app.css")
        middleware = LoginRequiredMiddleware(get_response=lambda request: None)

        self.assertIsNone(middleware.process_view(request, lambda request: None, (), {}))


class StaticAndComponentTests(SimpleTestCase):
    def test_static_files_resolve(self):
        expected = [
            "vendor/tabler/css/tabler.min.css",
            "vendor/tabler/js/tabler.min.js",
            "vendor/tabler/icons/tabler-icons.min.css",
            "vendor/tabler/icons/fonts/tabler-icons.woff2",
            "css/app.css",
            "js/app.js",
            "django_htmx/htmx-2.min.js",
        ]
        for path in expected:
            self.assertIsNotNone(finders.find(path), path)

    def test_tabler_version_is_pinned_in_the_stylesheet(self):
        css_path = finders.find("vendor/tabler/css/tabler.min.css")
        with open(css_path, encoding="utf-8", errors="ignore") as handle:
            header = handle.read(240)

        self.assertIn("1.6.1", header)

    def test_htmx_script_is_included_once_without_debug_extension(self):
        request = RequestFactory().get("/")
        html = render_to_string("base.html", {}, request=request)

        self.assertEqual(html.count("htmx-2.min.js"), 1)
        self.assertNotIn("django-htmx.js", html)
        self.assertIn("x-csrftoken", html)

    def test_empty_state_renders(self):
        html = render_to_string(
            "components/empty_state.html",
            {"title": "Sin datos", "message": "Nada que mostrar.", "icon": "ti-inbox"},
        )

        self.assertIn("Sin datos", html)
        self.assertIn("ti-inbox", html)

    def test_pagination_renders_for_a_page(self):
        page = Paginator(["a", "b", "c"], 1).page(2)
        html = render_to_string("components/pagination.html", {"page_obj": page})

        self.assertIn("Anterior", html)
        self.assertIn("Siguiente", html)
        self.assertIn("2 / 3", html)
