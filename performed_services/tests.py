from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clients.models import Client
from professionals.models import Professional
from reservations.models import Reservation
from services.models import Service

from .forms import ITEMS_REQUIRED, PerformedServiceForm, build_item_formset
from .models import CLIENT_MISMATCH, PerformedService, PerformedServiceItem

User = get_user_model()


def aware(year, month, day, hour, minute):
    return timezone.make_aware(datetime(year, month, day, hour, minute))


def make_client(**overrides):
    data = {"first_name": "Ana", "last_name": "Gomez"}
    data.update(overrides)
    return Client.objects.create(**data)


def make_professional(**overrides):
    data = {
        "first_name": "Lucia",
        "last_name": "Benitez",
        "identification_number": "4455667",
        "phone": "+595981100",
        "email": "lucia@example.com",
    }
    data.update(overrides)
    return Professional.objects.create(**data)


def make_service(**overrides):
    data = {
        "code": "GEL-001",
        "name": "Manicura",
        "price_gs": 70000,
        "duration_minutes": 60,
    }
    data.update(overrides)
    return Service.objects.create(**data)


def make_reservation(client, **overrides):
    data = {"client": client, "scheduled_at": aware(2026, 3, 15, 15, 0)}
    data.update(overrides)
    return Reservation.objects.create(**data)


def management(total, initial=0):
    return {
        "items-TOTAL_FORMS": str(total),
        "items-INITIAL_FORMS": str(initial),
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "30",
    }


def item_data(index, service, price, quantity=1, item_id=""):
    prefix = f"items-{index}"
    return {
        f"{prefix}-id": str(item_id),
        f"{prefix}-service": str(service.pk),
        f"{prefix}-unit_price_gs": str(price),
        f"{prefix}-quantity": str(quantity),
    }


class PerformedServiceModelTests(TestCase):
    def setUp(self):
        self.client_record = make_client()
        self.other_client = make_client(first_name="Beatriz", last_name="Diaz")
        self.professional = make_professional()
        self.service = make_service()
        self.reservation = make_reservation(self.client_record)

    def test_client_comes_from_the_reservation(self):
        attention = PerformedService(
            client=self.other_client,
            reservation=self.reservation,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        with self.assertRaises(ValidationError) as caught:
            attention.full_clean()
        self.assertEqual(caught.exception.message_dict["client"], [CLIENT_MISMATCH])

        attention.client = self.client_record
        attention.full_clean()
        attention.save()
        attention.refresh_from_db()

        self.assertEqual(attention.client, self.client_record)
        self.assertEqual(attention.additional_charge_gs, 0)
        self.assertEqual(attention.total_price_gs, 0)
        self.assertTrue(self.reservation.has_performed_services())
        self.assertTrue(self.client_record.has_service_history())
        self.assertTrue(self.professional.has_service_history())

    def test_attention_without_reservation_keeps_the_chosen_client(self):
        attention = PerformedService(
            client=self.client_record,
            professional=self.professional,
            performed_at=aware(2026, 3, 20, 11, 0),
            notes="  mostrador  ",
        )
        attention.full_clean()
        attention.save()
        attention.refresh_from_db()

        self.assertIsNone(attention.reservation)
        self.assertEqual(attention.notes, "mostrador")
        self.assertTrue(self.client_record.has_service_history())

    def test_the_same_reservation_cannot_be_used_twice(self):
        PerformedService.objects.create(
            client=self.client_record,
            reservation=self.reservation,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PerformedService.objects.create(
                    client=self.client_record,
                    reservation=self.reservation,
                    professional=self.professional,
                    performed_at=aware(2026, 3, 15, 17, 0),
                )

    def test_total_uses_historical_prices_and_the_extra_charge(self):
        pedicure = make_service(code="PED-001", name="Pedicura", price_gs=90000)
        attention = PerformedService.objects.create(
            client=self.client_record,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
            additional_charge_gs=15000,
            additional_charge_description="Diseño personalizado",
        )
        PerformedServiceItem.objects.create(
            performed_service=attention,
            service=self.service,
            unit_price_gs=70000,
            quantity=1,
        )
        PerformedServiceItem.objects.create(
            performed_service=attention,
            service=pedicure,
            unit_price_gs=90000,
            quantity=1,
        )
        attention.refresh_from_db()

        self.service.price_gs = 120000
        self.service.save()
        attention.refresh_from_db()
        self.assertEqual(attention.items.get(service=self.service).unit_price_gs, 70000)
        self.assertEqual(attention.total_price_gs, 175000)
        self.assertTrue(self.service.has_performed_services())

    def test_changing_items_refreshes_the_total_in_the_same_transaction(self):
        attention = PerformedService.objects.create(
            client=self.client_record,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        item = PerformedServiceItem.objects.create(
            performed_service=attention,
            service=self.service,
            unit_price_gs=70000,
            quantity=2,
        )
        attention.refresh_from_db()
        self.assertEqual(attention.total_price_gs, 140000)

        item.quantity = 1
        item.save()
        attention.refresh_from_db()
        self.assertEqual(attention.total_price_gs, 70000)

        item.delete()
        attention.refresh_from_db()
        self.assertEqual(attention.total_price_gs, 0)

    def test_quantity_must_be_positive(self):
        attention = PerformedService.objects.create(
            client=self.client_record,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        item = PerformedServiceItem(
            performed_service=attention,
            service=self.service,
            unit_price_gs=70000,
            quantity=0,
        )
        with self.assertRaises(ValidationError):
            item.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PerformedServiceItem.objects.create(
                    performed_service=attention,
                    service=self.service,
                    unit_price_gs=70000,
                    quantity=0,
                )

    def test_deleting_an_attention_removes_items_and_keeps_masters(self):
        attention = PerformedService.objects.create(
            client=self.client_record,
            reservation=self.reservation,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        item = PerformedServiceItem.objects.create(
            performed_service=attention,
            service=self.service,
            unit_price_gs=70000,
            quantity=1,
        )
        attention.delete()

        self.assertFalse(PerformedServiceItem.objects.filter(pk=item.pk).exists())
        self.assertTrue(Client.objects.filter(pk=self.client_record.pk).exists())
        self.assertTrue(Reservation.objects.filter(pk=self.reservation.pk).exists())
        self.assertTrue(Professional.objects.filter(pk=self.professional.pk).exists())
        self.assertTrue(Service.objects.filter(pk=self.service.pk).exists())
        self.assertFalse(self.reservation.has_performed_services())

    def test_masters_with_history_cannot_be_deleted(self):
        attention = PerformedService.objects.create(
            client=self.other_client,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        PerformedServiceItem.objects.create(
            performed_service=attention,
            service=self.service,
            unit_price_gs=70000,
            quantity=1,
        )

        for record in (self.other_client, self.professional, self.service):
            with self.assertRaises(ProtectedError):
                record.delete()


class PerformedServiceFormTests(TestCase):
    def setUp(self):
        self.client_record = make_client()
        self.professional = make_professional()
        self.inactive_professional = make_professional(
            first_name="Ines",
            last_name="Ruiz",
            identification_number="7788990",
            email="ines@example.com",
            is_active=False,
        )
        self.service = make_service()
        self.inactive_service = make_service(
            code="OFF-001",
            name="Retirado",
            price_gs=10000,
            is_active=False,
        )
        self.reservation = make_reservation(self.client_record)

    def test_create_switch_starts_on_and_edit_follows_the_record(self):
        create = PerformedServiceForm()
        self.assertTrue(create["has_reservation"].value())

        without = PerformedService.objects.create(
            client=self.client_record,
            professional=self.professional,
            performed_at=aware(2026, 3, 20, 11, 0),
        )
        edit = PerformedServiceForm(instance=without)
        self.assertFalse(edit["has_reservation"].value())

        with_reservation = PerformedService.objects.create(
            client=self.client_record,
            reservation=self.reservation,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        edit_linked = PerformedServiceForm(instance=with_reservation)
        self.assertTrue(edit_linked["has_reservation"].value())

    def test_new_rows_hide_inactive_services_and_keep_historical_prices(self):
        formset = build_item_formset(instance=PerformedService())
        choices = [choice[0] for choice in formset.forms[0].fields["service"].choices]
        self.assertIn(self.service.pk, choices)
        self.assertNotIn(self.inactive_service.pk, choices)

        attention = PerformedService.objects.create(
            client=self.client_record,
            professional=self.professional,
            performed_at=aware(2026, 3, 20, 11, 0),
        )
        item = PerformedServiceItem.objects.create(
            performed_service=attention,
            service=self.inactive_service,
            unit_price_gs=10000,
            quantity=1,
        )
        self.inactive_service.price_gs = 50000
        self.inactive_service.save()
        bound = build_item_formset(instance=attention)
        row = bound.forms[0]
        choices = [choice[0] for choice in row.fields["service"].choices]
        self.assertIn(self.inactive_service.pk, choices)
        self.assertEqual(row["unit_price_gs"].value(), item.unit_price_gs)

    def test_empty_item_list_is_rejected(self):
        attention = PerformedService()
        form = PerformedServiceForm(
            {
                "has_reservation": "on",
                "reservation": str(self.reservation.pk),
                "professional": str(self.professional.pk),
                "performed_at": "2026-03-15T16:00",
                "additional_charge_gs": "0",
                "additional_charge_description": "",
                "notes": "",
                **management(1),
            },
            instance=attention,
        )
        formset = build_item_formset(
            {
                **management(1),
                "items-0-id": "",
                "items-0-service": "",
                "items-0-unit_price_gs": "",
                "items-0-quantity": "1",
            },
            instance=attention,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(formset.is_valid())
        self.assertIn(ITEMS_REQUIRED, formset.non_form_errors())


class PerformedServiceViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("visitante", password="clave-segura")
        self.client.force_login(self.user)
        self.client_record = make_client(phone="+595981555", identification_number="1234567")
        self.other_client = make_client(first_name="Beatriz", last_name="Diaz")
        self.professional = make_professional()
        self.other_professional = make_professional(
            first_name="Marta",
            last_name="Ortiz",
            identification_number="1010101",
            email="marta@example.com",
        )
        self.manicure = make_service()
        self.pedicure = make_service(code="PED-001", name="Pedicura", price_gs=90000)
        self.reservation = make_reservation(self.client_record)

    def _payload(self, **overrides):
        data = {
            "has_reservation": "on",
            "reservation": str(self.reservation.pk),
            "client": str(self.other_client.pk),
            "professional": str(self.professional.pk),
            "performed_at": "2026-03-15T16:30",
            "notes": "Ventana",
            "additional_charge_gs": "15000",
            "additional_charge_description": "Diseño personalizado",
            **management(2),
            **item_data(0, self.manicure, 70000),
            **item_data(1, self.pedicure, 90000),
        }
        data.update(overrides)
        return data

    def test_create_with_reservation_derives_the_client(self):
        response = self.client.post(reverse("atenciones:nueva"), self._payload())
        attention = PerformedService.objects.get()

        self.assertRedirects(response, reverse("atenciones:detalle", kwargs={"pk": attention.pk}))
        self.assertEqual(attention.client, self.client_record)
        self.assertEqual(attention.reservation, self.reservation)
        self.assertEqual(attention.total_price_gs, 175000)
        self.assertEqual(attention.items.count(), 2)
        detail = self.client.get(reverse("atenciones:detalle", kwargs={"pk": attention.pk}))
        self.assertContains(detail, "Reserva #")
        self.assertContains(detail, "Gs. 175.000")
        self.assertContains(detail, "Diseño personalizado")

    def test_create_without_reservation_uses_the_selected_client(self):
        response = self.client.post(
            reverse("atenciones:nueva"),
            self._payload(
                has_reservation="",
                reservation="",
                client=str(self.other_client.pk),
                additional_charge_gs="0",
                additional_charge_description="",
            ),
        )
        attention = PerformedService.objects.get()

        self.assertRedirects(response, reverse("atenciones:detalle", kwargs={"pk": attention.pk}))
        self.assertIsNone(attention.reservation)
        self.assertEqual(attention.client, self.other_client)
        self.assertEqual(attention.total_price_gs, 160000)
        detail = self.client.get(reverse("atenciones:detalle", kwargs={"pk": attention.pk}))
        self.assertContains(detail, "Sin reserva")

    def test_create_page_starts_with_the_switch_on_and_can_add_a_client(self):
        response = self.client.get(reverse("atenciones:nueva"))

        self.assertTrue(response.context["has_reservation"])
        self.assertContains(response, 'id="client-mode" hidden')
        self.assertNotContains(response, 'id="reservation-mode" hidden')
        self.assertContains(response, "+ Nueva clienta")
        self.assertContains(response, 'id="new-client-modal"')
        self.assertContains(response, reverse("reservas:clienta_nueva"))

    def test_edit_page_reflects_a_walk_in_and_keeps_the_historical_price(self):
        attention = PerformedService.objects.create(
            client=self.client_record,
            professional=self.professional,
            performed_at=aware(2026, 3, 20, 11, 0),
        )
        PerformedServiceItem.objects.create(
            performed_service=attention,
            service=self.manicure,
            unit_price_gs=70000,
            quantity=1,
        )
        self.manicure.price_gs = 120000
        self.manicure.save()

        response = self.client.get(reverse("atenciones:editar", kwargs={"pk": attention.pk}))

        self.assertFalse(response.context["has_reservation"])
        self.assertContains(response, 'id="reservation-mode" hidden')
        self.assertContains(response, 'value="70000"')
        self.assertNotContains(response, "120000")

    def test_a_reservation_cannot_be_saved_twice(self):
        self.client.post(reverse("atenciones:nueva"), self._payload())
        response = self.client.post(reverse("atenciones:nueva"), self._payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elegí una reserva válida.")
        self.assertEqual(PerformedService.objects.count(), 1)

    def test_invalid_items_do_not_leave_an_attention(self):
        response = self.client.post(
            reverse("atenciones:nueva"),
            self._payload(**item_data(0, self.manicure, 70000, quantity=0)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PerformedService.objects.exists())
        self.assertFalse(PerformedServiceItem.objects.exists())

    def test_editing_items_updates_the_total(self):
        attention = PerformedService.objects.create(
            client=self.client_record,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 30),
            additional_charge_gs=15000,
        )
        first = PerformedServiceItem.objects.create(
            performed_service=attention,
            service=self.manicure,
            unit_price_gs=70000,
            quantity=1,
        )
        second = PerformedServiceItem.objects.create(
            performed_service=attention,
            service=self.pedicure,
            unit_price_gs=90000,
            quantity=1,
        )
        response = self.client.post(
            reverse("atenciones:editar", kwargs={"pk": attention.pk}),
            {
                "has_reservation": "",
                "reservation": "",
                "client": str(self.client_record.pk),
                "professional": str(self.professional.pk),
                "performed_at": "2026-03-15T16:30",
                "notes": "",
                "additional_charge_gs": "15000",
                "additional_charge_description": "",
                **management(2, initial=2),
                **item_data(0, self.manicure, 70000, item_id=first.pk),
                **item_data(1, self.pedicure, 90000, item_id=second.pk),
                "items-1-DELETE": "on",
            },
        )
        attention.refresh_from_db()

        self.assertRedirects(response, reverse("atenciones:detalle", kwargs={"pk": attention.pk}))
        self.assertFalse(PerformedServiceItem.objects.filter(pk=second.pk).exists())
        self.assertEqual(attention.total_price_gs, 85000)

    def test_list_filters_by_period_client_and_professional(self):
        PerformedService.objects.create(
            client=self.client_record,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        PerformedService.objects.create(
            client=self.other_client,
            professional=self.other_professional,
            performed_at=aware(2026, 4, 2, 10, 0),
        )

        by_period = self.client.get(
            reverse("atenciones:lista"),
            {"desde": "2026-03-01", "hasta": "2026-03-31"},
        )
        self.assertContains(by_period, "Gomez, Ana")
        self.assertNotContains(by_period, "Diaz, Beatriz")

        by_client = self.client.get(reverse("atenciones:lista"), {"q": "981555"})
        self.assertContains(by_client, "Gomez, Ana")
        self.assertNotContains(by_client, "Diaz, Beatriz")

        by_professional = self.client.get(
            reverse("atenciones:lista"),
            {"profesional": str(self.other_professional.pk)},
        )
        self.assertContains(by_professional, "Diaz, Beatriz")
        self.assertNotContains(by_professional, "Gomez, Ana")

    def test_delete_removes_the_attention_and_keeps_the_reservation(self):
        attention = PerformedService.objects.create(
            client=self.client_record,
            reservation=self.reservation,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        PerformedServiceItem.objects.create(
            performed_service=attention,
            service=self.manicure,
            unit_price_gs=70000,
            quantity=1,
        )
        response = self.client.post(
            reverse("atenciones:eliminar", kwargs={"pk": attention.pk})
        )

        self.assertRedirects(response, reverse("atenciones:lista"))
        self.assertFalse(PerformedService.objects.exists())
        self.assertFalse(PerformedServiceItem.objects.exists())
        self.assertTrue(Reservation.objects.filter(pk=self.reservation.pk).exists())
        reservation_page = self.client.get(
            reverse("reservas:detalle", kwargs={"pk": self.reservation.pk})
        )
        self.assertContains(reservation_page, "Esta reserva todavía no tiene servicios realizados.")

    def test_reservation_detail_links_the_attention(self):
        attention = PerformedService.objects.create(
            client=self.client_record,
            reservation=self.reservation,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        response = self.client.get(
            reverse("reservas:detalle", kwargs={"pk": self.reservation.pk})
        )

        self.assertContains(response, reverse("atenciones:detalle", kwargs={"pk": attention.pk}))
        self.assertNotContains(response, "Eliminar")

    def test_price_endpoint_copies_the_catalog_price(self):
        response = self.client.get(
            reverse("atenciones:precio_item"),
            {"prefix": "items-0", "items-0-service": str(self.manicure.pk)},
        )

        self.assertContains(response, 'name="items-0-unit_price_gs"')
        self.assertContains(response, 'value="70000"')
        self.assertNotContains(response, "<!DOCTYPE html>")

    def test_search_skips_reservations_already_used(self):
        other = make_reservation(self.other_client, scheduled_at=aware(2026, 3, 16, 9, 0))
        PerformedService.objects.create(
            client=self.client_record,
            reservation=self.reservation,
            professional=self.professional,
            performed_at=aware(2026, 3, 15, 16, 0),
        )
        response = self.client.get(
            reverse("atenciones:reservas_buscar"),
            {"q": "Gomez"},
        )
        self.assertNotContains(response, f"RES-{self.reservation.pk:04d}")
        self.other_client.identification_number = "7788990"
        self.other_client.save()
        by_name = self.client.get(
            reverse("atenciones:reservas_buscar"),
            {"reserva_q": "Diaz"},
        )
        code = f"RES-{other.pk:04d}"
        self.assertContains(by_name, code)
        self.assertContains(by_name, "Diaz, Beatriz")
        self.assertNotContains(by_name, "1234567")
        by_document = self.client.get(
            reverse("atenciones:reservas_buscar"),
            {"reserva_q": "7788990"},
        )
        self.assertContains(by_document, code)
        self.assertContains(by_document, "7788990")
        self.assertNotContains(by_document, f"RES-{self.reservation.pk:04d}")

    def test_select_shows_the_code_and_client_inside_the_field(self):
        response = self.client.get(
            reverse("atenciones:reserva_seleccionar", kwargs={"pk": self.reservation.pk}),
            HTTP_HX_REQUEST="true",
        )
        summary = f'RES-{self.reservation.pk:04d} · Gomez, Ana'

        self.assertContains(response, 'id="attention-reservation-picker"')
        self.assertContains(response, f'value="{summary}"')
        self.assertContains(response, "Quitar reserva")
        self.assertNotContains(response, "1234567")
        self.assertNotContains(response, "15/3/2026")
        self.assertContains(response, f'value="{self.reservation.pk}"')
