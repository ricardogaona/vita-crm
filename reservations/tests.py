from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clients.models import Client

from .models import Reservation, StatusChoices

User = get_user_model()


def aware(year, month, day, hour, minute):
    return timezone.make_aware(datetime(year, month, day, hour, minute))


class ReservationModelTests(TestCase):
    def setUp(self):
        self.client_record = Client.objects.create(first_name="Ana", last_name="Gomez")

    def test_defaults_leave_attended_at_empty(self):
        reservation = Reservation(
            client=self.client_record,
            scheduled_at=aware(2026, 3, 15, 15, 0),
        )
        reservation.full_clean()
        reservation.save()

        self.assertEqual(reservation.status, StatusChoices.PENDING)
        self.assertIsNone(reservation.attended_at)
        self.assertEqual(reservation.notes, "")
        self.assertFalse(reservation.has_performed_services())

    def test_attended_status_does_not_fill_attended_at(self):
        reservation = Reservation.objects.create(
            client=self.client_record,
            scheduled_at=aware(2026, 3, 15, 15, 0),
            status=StatusChoices.ATTENDED,
        )

        self.assertEqual(reservation.status, StatusChoices.ATTENDED)
        self.assertIsNone(reservation.attended_at)

    def test_past_appointment_is_valid(self):
        reservation = Reservation(
            client=self.client_record,
            scheduled_at=aware(2020, 1, 2, 8, 0),
            status=StatusChoices.ATTENDED,
            notes="  Vino sin turno  ",
        )
        reservation.full_clean()
        reservation.save()
        reservation.refresh_from_db()

        self.assertEqual(reservation.notes, "Vino sin turno")
        self.assertLess(reservation.scheduled_at, timezone.now())

    def test_status_outside_choices_is_rejected(self):
        reservation = Reservation(
            client=self.client_record,
            scheduled_at=aware(2026, 3, 15, 15, 0),
            status="pagada",
        )
        with self.assertRaises(ValidationError):
            reservation.full_clean()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Reservation.objects.create(
                    client=self.client_record,
                    scheduled_at=aware(2026, 3, 15, 15, 0),
                    status="pagada",
                )

    def test_client_with_reservations_cannot_be_deleted(self):
        Reservation.objects.create(
            client=self.client_record,
            scheduled_at=aware(2026, 3, 15, 15, 0),
        )

        self.assertTrue(self.client_record.has_service_history())
        with self.assertRaises(ProtectedError):
            self.client_record.delete()


class ReservationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("visitante", password="clave-segura")
        self.client.force_login(self.user)
        self.client_record = Client.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981555",
        )

    def _reservation(self, **kwargs):
        values = {
            "client": self.client_record,
            "scheduled_at": aware(2026, 3, 15, 15, 0),
            "status": StatusChoices.PENDING,
        }
        values.update(kwargs)
        return Reservation.objects.create(**values)

    def test_anonymous_user_goes_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("reservas:lista"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_create_requires_client_and_datetime(self):
        response = self.client.post(
            reverse("reservas:nueva"),
            {"status": StatusChoices.PENDING, "notes": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("client", response.context["form"].errors)
        self.assertIn("scheduled_at", response.context["form"].errors)
        self.assertContains(response, "Indicá la clienta.")
        self.assertContains(response, "Indicá la fecha y hora.")
        self.assertFalse(Reservation.objects.exists())

    def test_create_rejects_an_unknown_status(self):
        response = self.client.post(
            reverse("reservas:nueva"),
            {
                "client": self.client_record.pk,
                "scheduled_at": "2026-03-15T15:00",
                "status": "pagada",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.context["form"].errors)
        self.assertFalse(Reservation.objects.exists())

    def test_create_attended_in_the_past_leaves_attended_at_empty(self):
        response = self.client.post(
            reverse("reservas:nueva"),
            {
                "client": self.client_record.pk,
                "scheduled_at": "2020-01-02T08:00",
                "status": StatusChoices.ATTENDED,
                "attended_at": "",
                "notes": "  Vino sin turno  ",
            },
        )
        reservation = Reservation.objects.get()

        self.assertRedirects(
            response,
            reverse("reservas:detalle", kwargs={"pk": reservation.pk}),
        )
        self.assertEqual(reservation.status, StatusChoices.ATTENDED)
        self.assertIsNone(reservation.attended_at)
        self.assertEqual(reservation.notes, "Vino sin turno")
        self.assertEqual(
            timezone.localtime(reservation.scheduled_at),
            aware(2020, 1, 2, 8, 0),
        )

    def test_create_and_edit_pages_offer_a_new_client(self):
        created = self.client.get(reverse("reservas:nueva"))
        self.assertContains(created, "+ Nueva clienta")
        self.assertEqual(created.context["form"]["status"].value(), StatusChoices.PENDING)
        self.assertContains(created, 'id="new-client-modal"')

        reservation = self._reservation()
        edited = self.client.get(reverse("reservas:editar", kwargs={"pk": reservation.pk}))
        self.assertContains(edited, "+ Nueva clienta")
        self.assertNotContains(edited, "Seleccionada:")
        self.assertContains(edited, 'value="Gomez, Ana"')
        self.assertContains(edited, "Quitar clienta")
        self.assertContains(edited, "2026-03-15T15:00")

    def test_detail_shows_the_reservation_without_performed_services(self):
        reservation = self._reservation(notes="Ventana")
        response = self.client.get(reverse("reservas:detalle", kwargs={"pk": reservation.pk}))

        self.assertContains(response, "Gomez, Ana")
        self.assertContains(response, "Pendiente")
        self.assertContains(response, "Ventana")
        self.assertContains(response, "Esta reserva todavía no tiene servicios realizados.")
        self.assertContains(response, "Eliminar")

    def test_list_filters_by_client_date_and_status(self):
        other = Client.objects.create(first_name="Beatriz", last_name="Diaz", phone="+595981000")
        self._reservation()
        self._reservation(
            client=other,
            scheduled_at=aware(2026, 3, 16, 0, 30),
            status=StatusChoices.CANCELLED,
        )
        self._reservation(
            scheduled_at=aware(2026, 3, 15, 23, 30),
            status=StatusChoices.CONFIRMED,
        )

        by_client = self.client.get(reverse("reservas:lista"), {"q": "981555"})
        self.assertContains(by_client, "Gomez, Ana")
        self.assertNotContains(by_client, "Diaz, Beatriz")

        by_document = self.client.get(reverse("reservas:lista"), {"q": "1234567"})
        self.assertContains(by_document, "Gomez, Ana")
        self.assertNotContains(by_document, "Diaz, Beatriz")

        by_date = self.client.get(reverse("reservas:lista"), {"fecha": "2026-03-15"})
        self.assertContains(by_date, "Gomez, Ana")
        self.assertNotContains(by_date, "Diaz, Beatriz")

        by_status = self.client.get(reverse("reservas:lista"), {"estado": StatusChoices.CANCELLED})
        self.assertContains(by_status, "Diaz, Beatriz")
        self.assertNotContains(by_status, "Gomez, Ana")

    def test_list_pagination_keeps_the_query(self):
        listed = Client.objects.create(first_name="Nombre", last_name="Lista")
        for index in range(26):
            Reservation.objects.create(
                client=listed,
                scheduled_at=aware(2026, 4, 1, 9, 0),
                status=StatusChoices.PENDING,
            )

        page = self.client.get(reverse("reservas:lista"), {"q": "Lista", "page": 2})
        self.assertEqual(page.context["page_obj"].number, 2)
        self.assertContains(page, "q=Lista")
        self.assertContains(page, "page=1")

    def test_delete_removes_a_reservation_without_performed_services(self):
        reservation = self._reservation()
        response = self.client.post(
            reverse("reservas:eliminar", kwargs={"pk": reservation.pk})
        )

        self.assertRedirects(response, reverse("reservas:lista"))
        self.assertFalse(Reservation.objects.filter(pk=reservation.pk).exists())

    def test_delete_is_blocked_when_there_are_performed_services(self):
        reservation = self._reservation()
        with patch.object(Reservation, "has_performed_services", return_value=True):
            response = self.client.post(
                reverse("reservas:eliminar", kwargs={"pk": reservation.pk}),
                follow=True,
            )

        self.assertContains(response, "servicios realizados")
        self.assertTrue(Reservation.objects.filter(pk=reservation.pk).exists())

    def test_delete_rejects_get(self):
        reservation = self._reservation()
        response = self.client.get(reverse("reservas:eliminar", kwargs={"pk": reservation.pk}))
        self.assertEqual(response.status_code, 405)

    def test_client_delete_is_blocked_by_a_reservation(self):
        self._reservation()
        response = self.client.post(
            reverse("clientes:eliminar", kwargs={"pk": self.client_record.pk}),
            follow=True,
        )

        self.assertContains(response, "Podés desactivarla")
        self.assertTrue(Client.objects.filter(pk=self.client_record.pk).exists())


class ClientPickerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("visitante", password="clave-segura")
        self.client.force_login(self.user)
        self.client_record = Client.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981555",
        )

    def test_search_matches_name_document_and_phone(self):
        Client.objects.create(first_name="Beatriz", last_name="Diaz", phone="+595981000")

        for query in ("Ana", "Gomez", "1234567", "981555"):
            response = self.client.get(
                reverse("reservas:clientas_buscar"),
                {"q": query},
                HTTP_HX_REQUEST="true",
            )
            self.assertContains(response, "Gomez, Ana")
            self.assertNotContains(response, "Diaz, Beatriz")
            self.assertNotContains(response, "<!DOCTYPE html>")

    def test_select_replaces_the_picker_with_that_client(self):
        response = self.client.get(
            reverse("reservas:clienta_seleccionar", kwargs={"pk": self.client_record.pk}),
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, 'id="reservation-client-picker"')
        self.assertNotContains(response, "Seleccionada:")
        self.assertContains(response, 'value="Gomez, Ana"')
        self.assertContains(response, "Quitar clienta")
        self.assertContains(response, f'value="{self.client_record.pk}"')

    def test_modal_creates_a_client_with_name_only_and_selects_her(self):
        response = self.client.post(
            reverse("reservas:clienta_nueva"),
            {"first_name": "Carla", "last_name": "Lopez"},
            HTTP_HX_REQUEST="true",
        )
        created = Client.objects.get(first_name="Carla", last_name="Lopez")

        self.assertEqual(response.headers["HX-Trigger-After-Settle"], "closeNewClientModal")
        self.assertEqual(response.headers["HX-Reswap"], "none")
        self.assertNotIn("HX-Trigger", response.headers)
        self.assertContains(response, "hx-swap-oob")
        self.assertNotContains(response, "Seleccionada:")
        self.assertContains(response, 'value="Lopez, Carla"')
        self.assertContains(response, "Quitar clienta")
        self.assertContains(response, f'value="{created.pk}"')
        self.assertEqual(created.email, "")
        self.assertEqual(created.phone, "")
        self.assertFalse(created.marketing_consent)
        self.assertFalse(Reservation.objects.exists())

    def test_modal_validation_error_keeps_the_form_open(self):
        response = self.client.post(
            reverse("reservas:clienta_nueva"),
            {"first_name": "   ", "last_name": "Lopez", "email": "no-es-correo"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("HX-Trigger", response.headers)
        self.assertNotIn("HX-Trigger-After-Settle", response.headers)
        self.assertNotIn("HX-Reswap", response.headers)
        self.assertContains(response, 'id="id_first_name-error"')
        self.assertContains(response, 'id="id_email-error"')
        self.assertContains(response, 'id="new-client-modal-body"', count=0)
        self.assertFalse(Client.objects.filter(last_name="Lopez").exists())
        self.assertFalse(Reservation.objects.exists())
