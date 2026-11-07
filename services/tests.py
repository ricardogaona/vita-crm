from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse

from .admin import DEACTIVATE_INSTEAD, ServiceAdmin
from .models import (
    COST_MESSAGE,
    DURATION_MESSAGE,
    PRICE_MESSAGE,
    CategoryChoices,
    Service,
)

User = get_user_model()


def make_service(**overrides):
    data = {
        "code": "gel-001",
        "name": "Esmaltado semipermanente",
        "category": CategoryChoices.GEL,
        "price_gs": 150000,
        "estimated_cost_gs": 20000,
        "duration_minutes": 60,
    }
    data.update(overrides)
    return Service.objects.create(**data)


class ServiceModelTests(TestCase):
    def test_create_normalizes_code_and_name_and_starts_active(self):
        service = Service(
            code="  gel-001 ",
            name="  Esmaltado semipermanente  ",
            price_gs=150000,
            duration_minutes=60,
        )
        service.full_clean()
        service.save()
        service.refresh_from_db()

        self.assertEqual(service.code, "GEL-001")
        self.assertEqual(service.name, "Esmaltado semipermanente")
        self.assertEqual(service.category, "")
        self.assertIsNone(service.estimated_cost_gs)
        self.assertTrue(service.is_active)
        self.assertIsNotNone(service.created_at)
        self.assertIsNotNone(service.updated_at)
        self.assertEqual(str(service), "GEL-001 — Esmaltado semipermanente")
        self.assertFalse(service.has_performed_services())

    def test_blank_code_and_name_are_rejected(self):
        service = Service(code="   ", name="   ", price_gs=0, duration_minutes=1)
        with self.assertRaises(ValidationError) as caught:
            service.full_clean()
        self.assertIn("code", caught.exception.error_dict)
        self.assertIn("name", caught.exception.error_dict)

    def test_code_case_is_unique_in_validation_and_database(self):
        make_service(code="gel-001")
        duplicate = Service(
            code="GeL-001",
            name="Otro",
            price_gs=1,
            duration_minutes=1,
        )
        with self.assertRaises(ValidationError) as caught:
            duplicate.full_clean()
        self.assertIn("code", caught.exception.error_dict)

        other = make_service(code="acr-001", name="Acrílico")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Service.objects.filter(pk=other.pk).update(code="gel-001")

    def test_same_code_on_the_same_service_is_allowed(self):
        service = make_service(code="gel-001")
        service.code = "  gel-001 "
        service.full_clean()
        service.save()
        service.refresh_from_db()
        self.assertEqual(service.code, "GEL-001")

    def test_category_is_optional_and_limited_to_choices(self):
        service = make_service(category="")
        service.full_clean()

        service.category = "nails"
        with self.assertRaises(ValidationError) as caught:
            service.full_clean()
        self.assertIn("category", caught.exception.error_dict)

        labels = {choice.label for choice in CategoryChoices}
        self.assertEqual(
            labels,
            {
                "Gel",
                "Acrílico",
                "Soft Gel",
                "Remoción",
                "Manicura y pedicura",
                "Adicionales",
            },
        )

    def test_price_allows_zero_and_rejects_negative(self):
        service = Service(
            code="gel-002",
            name="Prueba",
            price_gs=0,
            duration_minutes=1,
        )
        service.full_clean()
        service.save()
        self.assertEqual(service.price_gs, 0)

        service.price_gs = -1
        with self.assertRaises(ValidationError) as caught:
            service.full_clean()
        self.assertEqual(caught.exception.message_dict["price_gs"], [PRICE_MESSAGE])

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Service.objects.filter(pk=service.pk).update(price_gs=-1)

    def test_estimated_cost_distinguishes_unknown_from_zero(self):
        unknown = make_service(code="gel-010", estimated_cost_gs=None)
        zero = make_service(code="gel-011", name="Costo cero", estimated_cost_gs=0)
        unknown.refresh_from_db()
        zero.refresh_from_db()

        self.assertIsNone(unknown.estimated_cost_gs)
        self.assertEqual(zero.estimated_cost_gs, 0)

        zero.estimated_cost_gs = -1
        with self.assertRaises(ValidationError) as caught:
            zero.full_clean()
        self.assertEqual(caught.exception.message_dict["estimated_cost_gs"], [COST_MESSAGE])

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Service.objects.filter(pk=zero.pk).update(estimated_cost_gs=-1)

    def test_duration_must_be_at_least_one_minute(self):
        service = Service(code="gel-003", name="Corto", price_gs=10, duration_minutes=1)
        service.full_clean()

        service.duration_minutes = 0
        with self.assertRaises(ValidationError) as caught:
            service.full_clean()
        self.assertEqual(
            caught.exception.message_dict["duration_minutes"],
            [DURATION_MESSAGE],
        )

        saved = make_service(code="gel-004", duration_minutes=15)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Service.objects.filter(pk=saved.pk).update(duration_minutes=0)

    def test_price_change_keeps_the_rest_of_the_catalog_row(self):
        service = make_service()
        created_at = service.created_at
        service.price_gs = 180000
        service.save()
        service.refresh_from_db()

        self.assertEqual(service.price_gs, 180000)
        self.assertEqual(service.estimated_cost_gs, 20000)
        self.assertEqual(service.code, "GEL-001")
        self.assertEqual(service.name, "Esmaltado semipermanente")
        self.assertEqual(service.duration_minutes, 60)
        self.assertEqual(service.created_at, created_at)


class ServiceAdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", "admin@example.com", "password")
        self.client.force_login(self.user)

    def test_changelist_searches_and_filters(self):
        gel = make_service(code="gel-001", name="Esmaltado", is_active=True)
        acrylic = make_service(
            code="acr-001",
            name="Uñas acrílicas",
            category=CategoryChoices.ACRYLIC,
            is_active=False,
        )
        url = reverse("admin:services_service_changelist")

        listed = self.client.get(url)
        self.assertContains(listed, gel.code)
        self.assertContains(listed, acrylic.name)
        for label in (
            "Gel",
            "Acrílico",
            "Soft Gel",
            "Remoción",
            "Manicura y pedicura",
            "Adicionales",
        ):
            self.assertContains(listed, label)

        found = self.client.get(url, {"q": "acrílicas"})
        self.assertContains(found, acrylic.code)
        self.assertNotContains(found, gel.code)

        by_category = self.client.get(url, {"category__exact": CategoryChoices.GEL})
        self.assertContains(by_category, gel.code)
        self.assertNotContains(by_category, acrylic.code)

        inactive = self.client.get(url, {"is_active__exact": "0"})
        self.assertContains(inactive, acrylic.code)
        self.assertNotContains(inactive, gel.code)

    def test_admin_creates_and_edits_without_touching_other_fields(self):
        response = self.client.post(
            reverse("admin:services_service_add"),
            {
                "code": " rem-001 ",
                "name": "  Remoción de gel ",
                "category": CategoryChoices.REMOVAL,
                "price_gs": "80000",
                "estimated_cost_gs": "",
                "duration_minutes": "30",
                "is_active": "on",
            },
        )
        service = Service.objects.get()
        self.assertRedirects(response, reverse("admin:services_service_changelist"))
        self.assertEqual(service.code, "REM-001")
        self.assertEqual(service.name, "Remoción de gel")
        self.assertIsNone(service.estimated_cost_gs)
        self.assertTrue(service.is_active)

        change_url = reverse("admin:services_service_change", args=[service.pk])
        change_page = self.client.get(change_url)
        self.assertNotContains(change_page, 'name="created_at"')
        self.assertNotContains(change_page, 'name="updated_at"')
        self.assertContains(change_page, "Precio de lista")
        self.assertContains(change_page, "sin remuneración")

        edited = self.client.post(
            change_url,
            {
                "code": service.code,
                "name": service.name,
                "category": service.category,
                "price_gs": "90000",
                "estimated_cost_gs": "0",
                "duration_minutes": service.duration_minutes,
                "is_active": "on",
            },
        )
        self.assertRedirects(edited, reverse("admin:services_service_changelist"))
        service.refresh_from_db()
        self.assertEqual(service.price_gs, 90000)
        self.assertEqual(service.estimated_cost_gs, 0)
        self.assertEqual(service.code, "REM-001")
        self.assertEqual(service.name, "Remoción de gel")
        self.assertEqual(service.duration_minutes, 30)

    def test_inactive_service_stays_available_in_admin(self):
        service = make_service(is_active=False)
        response = self.client.get(reverse("admin:services_service_change", args=[service.pk]))
        self.assertContains(response, service.code)
        self.assertContains(response, service.name)

    def test_service_without_history_can_be_deleted(self):
        service = make_service()
        response = self.client.post(
            reverse("admin:services_service_delete", args=[service.pk]),
            {"post": "yes"},
        )
        self.assertRedirects(response, reverse("admin:services_service_changelist"))
        self.assertFalse(Service.objects.filter(pk=service.pk).exists())

    def test_protected_delete_tells_to_deactivate(self):
        service = make_service()
        delete_url = reverse("admin:services_service_delete", args=[service.pk])
        with patch.object(
            ServiceAdmin,
            "get_deleted_objects",
            return_value=([], {}, set(), [service]),
        ):
            page = self.client.get(delete_url)
        self.assertContains(page, DEACTIVATE_INSTEAD)

        with patch.object(Service, "delete", side_effect=ProtectedError("blocked", {service})):
            with self.assertRaises(ProtectedError) as caught:
                self.client.post(delete_url, {"post": "yes"})
        self.assertEqual(caught.exception.args[0], DEACTIVATE_INSTEAD)

    def test_no_custom_frontend_routes(self):
        for path in ("/servicios/", "/services/"):
            with self.assertRaises(Resolver404):
                resolve(path)
        self.assertIn(Service, admin.site._registry)
