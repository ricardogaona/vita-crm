from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .forms import ProfessionalForm
from .models import Professional

User = get_user_model()


def payload(**overrides):
    data = {
        "first_name": "Ana",
        "last_name": "Gomez",
        "identification_number": "1234567",
        "phone": "+595981000000",
        "email": "ana@example.com",
        "is_active": "on",
        "start_date": "",
        "end_date": "",
        "notes": "",
    }
    data.update(overrides)
    return data


class ProfessionalModelTests(TestCase):
    def test_create_with_required_fields_starts_active(self):
        professional = Professional(
            first_name="  Ana  ",
            last_name="  Gomez ",
            identification_number="  0123456 ",
            phone="  +595 981 000000  ",
            email="  ana@example.com ",
        )
        professional.full_clean()
        professional.save()
        professional.refresh_from_db()

        self.assertEqual(professional.first_name, "Ana")
        self.assertEqual(professional.last_name, "Gomez")
        self.assertEqual(professional.identification_number, "0123456")
        self.assertEqual(professional.phone, "+595 981 000000")
        self.assertEqual(professional.email, "ana@example.com")
        self.assertEqual(professional.notes, "")
        self.assertIsNone(professional.start_date)
        self.assertIsNone(professional.end_date)
        self.assertTrue(professional.is_active)
        self.assertIsNotNone(professional.created_at)
        self.assertIsNotNone(professional.updated_at)
        self.assertFalse(professional.has_service_history())

    def test_blank_required_fields_are_rejected(self):
        professional = Professional(
            first_name="   ",
            last_name="   ",
            identification_number="   ",
            phone="   ",
            email="   ",
        )
        with self.assertRaises(ValidationError) as caught:
            professional.full_clean()
        for field in ("first_name", "last_name", "identification_number", "phone", "email"):
            self.assertIn(field, caught.exception.error_dict)

    def test_document_of_separators_only_is_rejected(self):
        professional = Professional(
            first_name="Ana",
            last_name="Gomez",
            identification_number=".- -",
            phone="+595981",
            email="ana@example.com",
        )
        with self.assertRaises(ValidationError) as caught:
            professional.full_clean()
        self.assertIn("identification_number", caught.exception.error_dict)

    def test_normalized_document_must_be_unique_but_leading_zeros_differ(self):
        Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1.234.567",
            phone="+595981",
            email="ana@example.com",
        )
        duplicate = Professional(
            first_name="Beatriz",
            last_name="Diaz",
            identification_number="1234567",
            phone="+595982",
            email="beatriz@example.com",
        )
        with self.assertRaises(ValidationError) as caught:
            duplicate.full_clean()
        self.assertIn("identification_number", caught.exception.error_dict)

        cased = Professional(
            first_name="Carla",
            last_name="Lopez",
            identification_number="ab-12",
            phone="+595983",
            email="carla@example.com",
        )
        cased.full_clean()
        cased.save()
        other_case = Professional(
            first_name="Dora",
            last_name="Ruiz",
            identification_number="AB12",
            phone="+595984",
            email="dora@example.com",
        )
        with self.assertRaises(ValidationError):
            other_case.full_clean()

        with_zero = Professional(
            first_name="Elena",
            last_name="Paz",
            identification_number="0123",
            phone="+595985",
            email="elena@example.com",
        )
        without_zero = Professional(
            first_name="Fabi",
            last_name="Paz",
            identification_number="123",
            phone="+595986",
            email="fabi@example.com",
        )
        with_zero.full_clean()
        with_zero.save()
        without_zero.full_clean()
        without_zero.save()

    def test_database_rejects_normalized_duplicate_and_invalid_dates(self):
        first = Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981",
            email="ana@example.com",
        )
        second = Professional.objects.create(
            first_name="Beatriz",
            last_name="Diaz",
            identification_number="999",
            phone="+595982",
            email="beatriz@example.com",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Professional.objects.filter(pk=second.pk).update(identification_number="123-4567")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Professional.objects.filter(pk=first.pk).update(
                    start_date=date(2024, 5, 2),
                    end_date=date(2024, 5, 1),
                )

    def test_same_document_on_the_same_professional_is_allowed(self):
        professional = Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1.234",
            phone="+595981",
            email="ana@example.com",
        )
        professional.identification_number = "12-34"
        professional.full_clean()
        professional.save()
        professional.refresh_from_db()
        self.assertEqual(professional.identification_number, "12-34")

    def test_phone_and_email_can_repeat(self):
        Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="111",
            phone="+595981",
            email="ana@example.com",
        )
        other = Professional(
            first_name="Ana",
            last_name="Lopez",
            identification_number="222",
            phone="+595981",
            email="ana@example.com",
        )
        other.full_clean()
        other.save()
        self.assertEqual(Professional.objects.filter(email="ana@example.com").count(), 2)

    def test_end_date_cannot_precede_start_date(self):
        professional = Professional(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981",
            email="ana@example.com",
            start_date=date(2024, 3, 2),
            end_date=date(2024, 3, 1),
        )
        with self.assertRaises(ValidationError) as caught:
            professional.full_clean()
        self.assertIn("end_date", caught.exception.error_dict)

        professional.end_date = date(2024, 3, 2)
        professional.full_clean()

        paused = Professional(
            first_name="Lia",
            last_name="Perez",
            identification_number="7654321",
            phone="+595982",
            email="lia@example.com",
            is_active=False,
        )
        paused.full_clean()
        paused.save()
        self.assertFalse(paused.is_active)
        self.assertIsNone(paused.end_date)

    def test_dates_do_not_change_active_flag(self):
        professional = Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981",
            email="ana@example.com",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 2, 1),
            is_active=True,
        )
        professional.refresh_from_db()
        self.assertTrue(professional.is_active)

    def test_search_requires_every_term_and_status_filter(self):
        Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981555",
            email="ana@example.com",
            is_active=True,
        )
        Professional.objects.create(
            first_name="Beatriz",
            last_name="Diaz",
            identification_number="999",
            phone="+595981000",
            email="beatriz@example.com",
            is_active=False,
        )

        self.assertEqual(
            set(Professional.objects.search("Ana Gomez").values_list("first_name", flat=True)),
            {"Ana"},
        )
        self.assertEqual(
            set(Professional.objects.search("1234567").values_list("first_name", flat=True)),
            {"Ana"},
        )
        self.assertEqual(
            set(Professional.objects.search("981555").values_list("first_name", flat=True)),
            {"Ana"},
        )
        self.assertEqual(
            set(Professional.objects.search("ana@example.com").values_list("first_name", flat=True)),
            {"Ana"},
        )
        self.assertFalse(Professional.objects.search("Ana Beatriz").exists())
        self.assertEqual(
            set(Professional.objects.by_status("inactivas").values_list("first_name", flat=True)),
            {"Beatriz"},
        )
        self.assertEqual(Professional.objects.by_status("").count(), 2)

    def test_commission_stays_empty_until_it_is_set(self):
        professional = Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981",
            email="ana@example.com",
        )
        professional.refresh_from_db()
        self.assertIsNone(professional.commission)

        professional.commission = Decimal("37.50")
        professional.save()
        professional.refresh_from_db()
        self.assertEqual(professional.commission, Decimal("37.50"))

        professional.commission = Decimal("25")
        professional.save()
        professional.refresh_from_db()
        self.assertEqual(professional.commission, Decimal("25.00"))


class ProfessionalFormTests(TestCase):
    def test_save_normalizes_text_and_starts_active(self):
        form = ProfessionalForm(
            payload(
                first_name="  Ana  ",
                last_name=" Gomez ",
                phone="+595 981 111",
                email="  ana@example.com  ",
            )
        )

        self.assertTrue(form.is_valid(), form.errors)
        professional = form.save()

        self.assertEqual(professional.first_name, "Ana")
        self.assertEqual(professional.last_name, "Gomez")
        self.assertEqual(professional.phone, "+595 981 111")
        self.assertEqual(professional.email, "ana@example.com")
        self.assertTrue(professional.is_active)
        self.assertIsNotNone(professional.created_at)

    def test_unbound_form_defaults_to_active_without_timestamps(self):
        form = ProfessionalForm()

        self.assertTrue(form["is_active"].value())
        self.assertNotIn("created_at", form.fields)
        self.assertNotIn("updated_at", form.fields)

    def test_blank_name_shows_a_form_error(self):
        form = ProfessionalForm(payload(first_name="   "))

        self.assertFalse(form.is_valid())
        self.assertIn("first_name", form.errors)
        self.assertIn("Indicá el nombre.", form.errors["first_name"])
        self.assertFalse(Professional.objects.exists())

    def test_invalid_email_shows_a_form_error(self):
        form = ProfessionalForm(payload(email="no-es-correo"))

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertFalse(Professional.objects.exists())

    def test_duplicate_document_shows_a_form_error(self):
        Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1.234.567",
            phone="+595981",
            email="ana@example.com",
        )
        form = ProfessionalForm(
            payload(
                first_name="Beatriz",
                identification_number="1234567",
                email="beatriz@example.com",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("identification_number", form.errors)
        self.assertIn(
            "Ya hay una profesional con este documento.",
            form.errors["identification_number"],
        )
        self.assertEqual(Professional.objects.count(), 1)

    def test_edit_stores_optional_dates_and_can_deactivate(self):
        professional = Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981",
            email="ana@example.com",
        )
        form = ProfessionalForm(
            payload(
                phone="+595981000",
                email="ana@spa.test",
                start_date="2024-03-15",
                end_date="2024-03-15",
                notes="Turno mañana.",
                is_active="",
            ),
            instance=professional,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        professional.refresh_from_db()
        self.assertEqual(professional.phone, "+595981000")
        self.assertEqual(professional.email, "ana@spa.test")
        self.assertEqual(professional.start_date, date(2024, 3, 15))
        self.assertEqual(professional.end_date, date(2024, 3, 15))
        self.assertEqual(professional.notes, "Turno mañana.")
        self.assertFalse(professional.is_active)
        self.assertIsNotNone(professional.updated_at)

    def test_end_date_before_start_is_rejected_on_the_form(self):
        professional = Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981",
            email="ana@example.com",
        )
        form = ProfessionalForm(
            payload(start_date="2024-04-02", end_date="2024-04-01"),
            instance=professional,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)
        professional.refresh_from_db()
        self.assertIsNone(professional.end_date)


class ProfessionalAdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@example.com", "password")
        self.client.force_login(self.user)

    def test_admin_creates_and_edits_commission(self):
        response = self.client.post(
            reverse("admin:professionals_professional_add"),
            {
                "first_name": "Ana",
                "last_name": "Gomez",
                "identification_number": "1234567",
                "phone": "+595981",
                "email": "ana@example.com",
                "is_active": "on",
                "commission": "37.50",
                "start_date": "",
                "end_date": "",
                "notes": "",
            },
        )
        professional = Professional.objects.get()
        self.assertRedirects(response, reverse("admin:professionals_professional_changelist"))
        self.assertEqual(professional.commission, Decimal("37.50"))

        change_url = reverse("admin:professionals_professional_change", args=[professional.pk])
        edited = self.client.post(
            change_url,
            {
                "first_name": professional.first_name,
                "last_name": professional.last_name,
                "identification_number": professional.identification_number,
                "phone": professional.phone,
                "email": professional.email,
                "is_active": "on",
                "commission": "25.00",
                "start_date": "",
                "end_date": "",
                "notes": "",
            },
        )
        self.assertRedirects(edited, reverse("admin:professionals_professional_changelist"))
        professional.refresh_from_db()
        self.assertEqual(professional.commission, Decimal("25.00"))
        self.assertEqual(professional.first_name, "Ana")
        self.assertEqual(professional.email, "ana@example.com")


class ProfessionalViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("visitante", password="clave-segura")
        self.client.force_login(self.user)

    def test_anonymous_user_goes_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("profesionales:lista"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
        self.assertIn("next=/profesionales/", response.url)

    def test_list_has_no_create_action(self):
        response = self.client.get(reverse("profesionales:lista"))

        self.assertNotContains(response, "Nueva profesional")

    def test_write_routes_are_not_published(self):
        professional = Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981",
            email="ana@example.com",
        )
        paths = [
            "/profesionales/nueva/",
            f"/profesionales/{professional.pk}/editar/",
            f"/profesionales/{professional.pk}/desactivar/",
            f"/profesionales/{professional.pk}/eliminar/",
        ]

        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 404)
            self.assertEqual(self.client.post(path, payload()).status_code, 404)

        professional.refresh_from_db()
        self.assertTrue(professional.is_active)
        self.assertEqual(Professional.objects.count(), 1)

    def test_inactive_professional_stays_in_the_filtered_list(self):
        Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="111",
            phone="+595981555",
            email="ana@example.com",
            start_date=date(2024, 1, 2),
        )
        Professional.objects.create(
            first_name="Beatriz",
            last_name="Diaz",
            identification_number="222",
            phone="+595981000",
            email="beatriz@example.com",
            is_active=False,
        )

        found = self.client.get(reverse("profesionales:lista"), {"q": "Gomez"})
        self.assertContains(found, "Gomez, Ana")
        self.assertContains(found, "Activa")
        self.assertContains(found, "2/1/2024")
        self.assertNotContains(found, "Beatriz")

        inactive = self.client.get(reverse("profesionales:lista"), {"estado": "inactivas"})
        self.assertContains(inactive, "Inactiva")
        self.assertContains(inactive, "Beatriz")
        self.assertNotContains(inactive, "Gomez, Ana")

    def test_search_list_and_pagination_keep_the_query(self):
        for index in range(26):
            Professional.objects.create(
                first_name=f"Nombre{index:02d}",
                last_name="Lista",
                identification_number=f"{index:05d}",
                phone="+595981000",
                email=f"lista{index:02d}@example.com",
            )

        page = self.client.get(
            reverse("profesionales:lista"),
            {"q": "Lista", "estado": "activas", "page": 2},
        )
        self.assertEqual(page.context["page_obj"].number, 2)
        self.assertContains(page, "q=Lista")
        self.assertContains(page, "estado=activas")
        self.assertContains(page, "page=1")

    def test_detail_shows_contact_and_pending_history(self):
        professional = Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            identification_number="1234567",
            phone="+595981",
            email="ana@example.com",
        )
        response = self.client.get(
            reverse("profesionales:detalle", kwargs={"pk": professional.pk})
        )

        self.assertContains(response, "Gomez, Ana")
        self.assertContains(response, "ana@example.com")
        self.assertContains(response, "Comisión")
        self.assertContains(
            response,
            '<div class="datagrid-title">Comisión</div><div class="datagrid-content">—</div>',
            html=True,
        )
        self.assertContains(response, "Creada")

        professional.commission = Decimal("37.50")
        professional.save()
        with_commission = self.client.get(
            reverse("profesionales:detalle", kwargs={"pk": professional.pk})
        )
        self.assertContains(with_commission, "37,50%")
        self.assertContains(response, "Esta profesional todavía no tiene servicios realizados.")
        self.assertContains(response, reverse("profesionales:lista"))
        self.assertNotContains(response, "Editar")
        self.assertNotContains(response, "Desactivar")
        self.assertNotContains(response, "Eliminar")
