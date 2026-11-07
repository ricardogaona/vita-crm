from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Client

User = get_user_model()


class ClientModelTests(TestCase):
    def test_create_with_name_only_leaves_optional_fields_empty(self):
        client = Client(first_name="Ana", last_name="Gomez")
        client.full_clean()
        client.save()

        self.assertEqual(client.identification_number, "")
        self.assertEqual(client.tax_id, "")
        self.assertEqual(client.tax_name, "")
        self.assertEqual(client.phone, "")
        self.assertEqual(client.email, "")
        self.assertEqual(client.source, "")
        self.assertEqual(client.notes, "")
        self.assertIsNone(client.referred_by)
        self.assertIsNone(client.first_contact_date)
        self.assertTrue(client.is_active)
        self.assertFalse(client.marketing_consent)
        self.assertIsNone(client.marketing_consent_at)
        self.assertFalse(client.has_service_history())

    def test_phone_does_not_imply_marketing_consent(self):
        client = Client.objects.create(
            first_name="Ana",
            last_name="Gomez",
            phone="+595981000000",
        )

        self.assertFalse(client.marketing_consent)
        self.assertIsNone(client.marketing_consent_at)

    def test_whitespace_names_are_stripped_and_blank_names_rejected(self):
        client = Client(first_name="  Ana  ", last_name="  Gomez ")
        client.full_clean()
        client.save()
        client.refresh_from_db()

        self.assertEqual(client.first_name, "Ana")
        self.assertEqual(client.last_name, "Gomez")

        blank = Client(first_name="   ", last_name="   ")
        with self.assertRaises(ValidationError) as caught:
            blank.full_clean()
        self.assertIn("first_name", caught.exception.error_dict)
        self.assertIn("last_name", caught.exception.error_dict)

    def test_marketing_consent_sets_timestamp_once(self):
        client = Client.objects.create(first_name="Ana", last_name="Gomez")
        self.assertIsNone(client.marketing_consent_at)

        client.marketing_consent = True
        client.save()
        client.refresh_from_db()
        stamp = client.marketing_consent_at
        self.assertIsNotNone(stamp)

        client.marketing_consent = False
        client.save()
        client.refresh_from_db()
        self.assertFalse(client.marketing_consent)
        self.assertEqual(client.marketing_consent_at, stamp)

    def test_self_referral_is_rejected(self):
        client = Client.objects.create(first_name="Ana", last_name="Gomez")
        client.referred_by = client

        with self.assertRaises(ValidationError) as caught:
            client.full_clean()
        self.assertIn("referred_by", caught.exception.error_dict)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Client.objects.filter(pk=client.pk).update(referred_by_id=client.pk)

    def test_referral_without_source_is_allowed(self):
        referrer = Client.objects.create(first_name="Lia", last_name="Perez")
        client = Client(
            first_name="Ana",
            last_name="Gomez",
            referred_by=referrer,
            source="",
        )
        client.full_clean()
        client.save()

        referrer.delete()
        client.refresh_from_db()
        self.assertIsNone(client.referred_by)

    def test_same_email_can_be_stored_twice(self):
        Client.objects.create(first_name="Ana", last_name="Gomez", email="ana@example.com")
        other = Client(first_name="Ana", last_name="Lopez", email="ana@example.com")
        other.full_clean()
        other.save()

        self.assertEqual(Client.objects.filter(email="ana@example.com").count(), 2)

    def test_search_requires_every_term(self):
        Client.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981555",
            email="ana@example.com",
        )
        Client.objects.create(first_name="Beatriz", last_name="Diaz", phone="+595981000")

        names = set(Client.objects.search("Ana Gomez").values_list("first_name", flat=True))
        self.assertEqual(names, {"Ana"})
        self.assertEqual(
            set(Client.objects.search("1234567").values_list("first_name", flat=True)),
            {"Ana"},
        )
        self.assertEqual(
            set(Client.objects.search("981555").values_list("first_name", flat=True)),
            {"Ana"},
        )
        self.assertEqual(
            set(Client.objects.search("ana@example.com").values_list("first_name", flat=True)),
            {"Ana"},
        )
        self.assertFalse(Client.objects.search("Ana Beatriz").exists())


class ClientViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("visitante", password="clave-segura")
        self.client.force_login(self.user)

    def test_anonymous_user_goes_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("clientes:lista"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
        self.assertIn("next=/clientes/", response.url)

    def test_create_with_name_only(self):
        response = self.client.post(
            reverse("clientes:nueva"),
            {"first_name": "  Ana  ", "last_name": " Gomez ", "is_active": "on"},
        )
        client = Client.objects.get()

        self.assertRedirects(response, reverse("clientes:detalle", kwargs={"pk": client.pk}))
        self.assertEqual(client.first_name, "Ana")
        self.assertEqual(client.last_name, "Gomez")
        self.assertEqual(client.email, "")
        self.assertFalse(client.marketing_consent)
        self.assertIsNone(client.marketing_consent_at)
        self.assertTrue(client.is_active)

    def test_create_form_defaults(self):
        response = self.client.get(reverse("clientes:nueva"))
        form = response.context["form"]

        self.assertFalse(form["marketing_consent"].value())
        self.assertTrue(form["is_active"].value())
        self.assertContains(response, "novalidate")

    def test_blank_name_shows_a_form_error(self):
        response = self.client.post(
            reverse("clientes:nueva"),
            {"first_name": "   ", "last_name": "Gomez"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("first_name", response.context["form"].errors)
        self.assertFalse(Client.objects.exists())

    def test_invalid_email_shows_a_form_error(self):
        response = self.client.post(
            reverse("clientes:nueva"),
            {
                "first_name": "Ana",
                "last_name": "Gomez",
                "email": "no-es-correo",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        error = response.context["form"].errors["email"][0]
        self.assertContains(response, error)
        self.assertFalse(Client.objects.exists())

    def test_edit_can_store_optional_data_and_deactivate(self):
        client = Client.objects.create(first_name="Ana", last_name="Gomez")
        referrer = Client.objects.create(first_name="Lia", last_name="Perez")

        response = self.client.post(
            reverse("clientes:editar", kwargs={"pk": client.pk}),
            {
                "first_name": "Ana",
                "last_name": "Gomez",
                "phone": "+595981",
                "email": "ana@example.com",
                "source": "referido",
                "referred_by": referrer.pk,
                "first_contact_date": "2024-03-15",
                "marketing_consent": "on",
                "notes": "Prefiere la mañana.",
            },
        )

        self.assertRedirects(response, reverse("clientes:detalle", kwargs={"pk": client.pk}))
        client.refresh_from_db()
        self.assertEqual(client.phone, "+595981")
        self.assertEqual(client.email, "ana@example.com")
        self.assertEqual(client.source, "referido")
        self.assertEqual(client.referred_by, referrer)
        self.assertEqual(client.first_contact_date, date(2024, 3, 15))
        self.assertTrue(client.marketing_consent)
        self.assertIsNotNone(client.marketing_consent_at)
        self.assertLessEqual(client.marketing_consent_at, timezone.now())
        self.assertFalse(client.is_active)
        self.assertEqual(client.notes, "Prefiere la mañana.")

    def test_self_referral_is_rejected_on_the_form(self):
        client = Client.objects.create(first_name="Ana", last_name="Gomez")

        response = self.client.post(
            reverse("clientes:editar", kwargs={"pk": client.pk}),
            {
                "first_name": "Ana",
                "last_name": "Gomez",
                "referred_by": client.pk,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("referred_by", response.context["form"].errors)
        client.refresh_from_db()
        self.assertIsNone(client.referred_by)

    def test_search_list_and_pagination_keep_the_query(self):
        Client.objects.create(first_name="Ana", last_name="Gomez", phone="+595981555")
        Client.objects.create(first_name="Beatriz", last_name="Diaz")
        for index in range(26):
            Client.objects.create(first_name=f"Nombre{index:02d}", last_name="Lista")

        found = self.client.get(reverse("clientes:lista"), {"q": "Gomez"})
        self.assertContains(found, "Ana")
        self.assertNotContains(found, "Beatriz")

        page = self.client.get(reverse("clientes:lista"), {"q": "Lista", "page": 2})
        self.assertEqual(page.context["page_obj"].number, 2)
        self.assertContains(page, "q=Lista")
        self.assertContains(page, "page=1")

    def test_detail_shows_the_client(self):
        client = Client.objects.create(
            first_name="Ana",
            last_name="Gomez",
            email="ana@example.com",
        )

        response = self.client.get(reverse("clientes:detalle", kwargs={"pk": client.pk}))

        self.assertContains(response, "Gomez, Ana")
        self.assertContains(response, "ana@example.com")
        self.assertContains(response, "Creada")
        self.assertNotContains(response, "Reserva")

    def test_delete_removes_a_client_without_history(self):
        client = Client.objects.create(first_name="Ana", last_name="Gomez")

        response = self.client.post(reverse("clientes:eliminar", kwargs={"pk": client.pk}))

        self.assertRedirects(response, reverse("clientes:lista"))
        self.assertFalse(Client.objects.filter(pk=client.pk).exists())

    def test_delete_is_blocked_when_there_is_service_history(self):
        client = Client.objects.create(first_name="Ana", last_name="Gomez")

        with patch.object(Client, "has_service_history", return_value=True):
            response = self.client.post(
                reverse("clientes:eliminar", kwargs={"pk": client.pk}),
                follow=True,
            )

        self.assertContains(response, "Podés desactivarla")
        self.assertTrue(Client.objects.filter(pk=client.pk).exists())

    def test_delete_rejects_get(self):
        client = Client.objects.create(first_name="Ana", last_name="Gomez")
        response = self.client.get(reverse("clientes:eliminar", kwargs={"pk": client.pk}))
        self.assertEqual(response.status_code, 405)
