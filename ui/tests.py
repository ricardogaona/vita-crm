from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from config.middleware import LoginRequiredMiddleware

User = get_user_model()


def login_url_for(path):
    return f"{reverse('admin:login')}?next={path}"


@override_settings(DEBUG=True)
class DemoPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("visitante", password="clave-segura")
        self.client.force_login(self.user)

    def test_get_returns_full_page(self):
        response = self.client.get(reverse("ui:demo"))

        self.assertContains(response, "<!DOCTYPE html>")
        self.assertContains(response, 'lang="es"')
        self.assertContains(response, "Demostración")
        self.assertContains(response, "tabler.min.css")
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'hx-headers')
        self.assertContains(response, "x-csrftoken")

    def test_assets_are_local_and_htmx_loads_once(self):
        response = self.client.get(reverse("ui:demo"))
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

    def test_htmx_get_returns_fragment(self):
        response = self.client.get(reverse("ui:status"), HTTP_HX_REQUEST="true")
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Estado generado por el servidor", html)
        self.assertNotIn("<!DOCTYPE html>", html)
        self.assertNotIn("tabler.min.css", html)
        self.assertNotIn("<html", html)
        self.assertIn("HX-Request", response.headers["Vary"])

    def test_status_get_without_htmx_returns_full_page(self):
        response = self.client.get(reverse("ui:status"))

        self.assertContains(response, "<!DOCTYPE html>")
        self.assertContains(response, "Estado generado por el servidor")

    def test_htmx_post_valid_returns_confirmation_fragment(self):
        response = self.client.post(
            reverse("ui:demo"),
            {"name": "Ana <b>", "message": "Mensaje de prueba válido."},
            HTTP_HX_REQUEST="true",
        )
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("se validó correctamente", html)
        self.assertIn("Ana &lt;b&gt;", html)
        self.assertNotIn("<b>", html)
        self.assertNotIn("<!DOCTYPE html>", html)
        self.assertIn('id="demo-form-region"', html)

    def test_htmx_post_invalid_shows_field_errors(self):
        response = self.client.post(
            reverse("ui:demo"),
            {"name": "A", "message": "corto"},
            HTTP_HX_REQUEST="true",
        )
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="id_name-error"', html)
        self.assertIn('id="id_message-error"', html)
        self.assertIn("is-invalid", html)
        self.assertNotIn("<!DOCTYPE html>", html)

    def test_post_without_javascript_invalid_renders_full_page(self):
        response = self.client.post(
            reverse("ui:demo"),
            {"name": "", "message": "corto"},
        )

        self.assertContains(response, "<!DOCTYPE html>")
        self.assertContains(response, 'id="id_name-error"')
        self.assertContains(response, 'id="id_message-error"')

    def test_post_without_javascript_valid_redirects_with_message(self):
        response = self.client.post(
            reverse("ui:demo"),
            {"name": "Ana", "message": "Mensaje de prueba válido."},
            follow=True,
        )

        self.assertEqual(response.redirect_chain, [(reverse("ui:demo"), 302)])
        self.assertContains(response, "alert-success")
        self.assertContains(response, "Ana")

    def test_csrf_rejects_htmx_post_without_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            reverse("ui:demo"),
            {"name": "Ana", "message": "Mensaje de prueba válido."},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 403)

    def test_csrf_accepts_htmx_header(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("ui:demo"))
        token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("ui:demo"),
            {"name": "Ana", "message": "Mensaje de prueba válido."},
            HTTP_HX_REQUEST="true",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertContains(response, "se validó correctamente")

    def test_csrf_accepts_form_token_without_htmx(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("ui:demo"))
        token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("ui:demo"),
            {
                "name": "Ana",
                "message": "Mensaje de prueba válido.",
                "csrfmiddlewaretoken": token,
            },
        )

        self.assertEqual(response.status_code, 302)

    def test_status_post_is_rejected(self):
        response = self.client.post(reverse("ui:status"))

        self.assertEqual(response.status_code, 405)

    def test_demo_response_varies_on_htmx_header(self):
        response = self.client.get(reverse("ui:demo"))

        self.assertIn("HX-Request", response.headers["Vary"])


@override_settings(DEBUG=False)
class DemoDisabledTests(TestCase):
    def test_anonymous_page_redirects_to_login(self):
        response = self.client.get(reverse("ui:demo"))

        self.assertRedirects(response, login_url_for(reverse("ui:demo")))

    def test_anonymous_htmx_fragment_redirects_to_login(self):
        path = reverse("ui:status")
        response = self.client.get(path, HTTP_HX_REQUEST="true")

        self.assertEqual(response.headers["HX-Redirect"], login_url_for(path))
        self.assertNotIn("<!DOCTYPE html>", response.content.decode())

    def test_authenticated_page_is_hidden(self):
        self.client.force_login(User.objects.create_user("visitante", password="clave-segura"))
        response = self.client.get(reverse("ui:demo"))

        self.assertEqual(response.status_code, 404)

    def test_authenticated_htmx_fragment_is_hidden(self):
        self.client.force_login(User.objects.create_user("visitante", password="clave-segura"))
        response = self.client.get(reverse("ui:status"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 404)

    def test_htmx_script_is_included_once_without_debug_extension(self):
        request = RequestFactory().get("/")
        html = render_to_string("base.html", {}, request=request)

        self.assertEqual(html.count("htmx-2.min.js"), 1)
        self.assertNotIn("django-htmx.js", html)
        self.assertIn("x-csrftoken", html)


class LoginRequiredTests(TestCase):
    def test_anonymous_demo_redirects_to_admin_login(self):
        path = reverse("ui:demo")
        response = self.client.get(path)

        self.assertRedirects(response, login_url_for(path))
        self.assertIn("HX-Request", response.headers["Vary"])

    def test_anonymous_status_redirects_to_admin_login(self):
        path = reverse("ui:status")
        response = self.client.get(path)

        self.assertRedirects(response, login_url_for(path))

    def test_anonymous_admin_index_redirects_to_admin_login(self):
        path = reverse("admin:index")
        response = self.client.get(path)

        self.assertRedirects(response, login_url_for(path))

    def test_anonymous_htmx_redirects_without_layout(self):
        path = reverse("ui:demo")
        response = self.client.get(path, HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["HX-Redirect"], login_url_for(path))
        self.assertIn("HX-Request", response.headers["Vary"])
        self.assertNotIn("tabler.min.css", response.content.decode())
        self.assertNotIn("<!DOCTYPE html>", response.content.decode())

    def test_anonymous_post_to_status_redirects_before_method_check(self):
        path = reverse("ui:status")
        response = self.client.post(path)

        self.assertRedirects(response, login_url_for(path))

    def test_admin_login_is_public(self):
        response = self.client.get(reverse("admin:login"))

        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True)
    def test_staff_login_returns_to_requested_page(self):
        User.objects.create_user("ana", password="clave-segura", is_staff=True)
        next_url = reverse("ui:demo")
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
