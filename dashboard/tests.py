import re
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from clients.models import Client
from performed_services.models import PerformedService, PerformedServiceItem
from professionals.models import Professional
from reservations.models import Reservation, StatusChoices
from services.models import Service

from .queries import (
    ASUNCION,
    ERROR_INVALID,
    ERROR_MISSING,
    ERROR_RANGE,
    attention_kpis,
    chart_payload,
    evolution_chart,
    inclusive_days,
    midnight,
    recent_attentions,
    reservation_split,
    reservation_statuses,
    resolve_period,
    top_services,
    uses_monthly,
)

User = get_user_model()


def at(year, month, day, hour=10, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=ASUNCION)


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


def make_attention(client, professional, performed_at, **overrides):
    data = {
        "client": client,
        "professional": professional,
        "performed_at": performed_at,
    }
    data.update(overrides)
    return PerformedService.objects.create(**data)


class PeriodTests(SimpleTestCase):
    def test_presets_use_asuncion_bounds(self):
        sunday = date(2026, 11, 8)
        self.assertEqual(sunday.weekday(), 6)

        today = resolve_period("hoy", "", "", today=sunday)
        self.assertEqual(today.start, midnight(sunday))
        self.assertEqual(today.end, midnight(date(2026, 11, 9)))

        week = resolve_period("semana", "", "", today=sunday)
        self.assertEqual(week.start, midnight(date(2026, 11, 2)))
        self.assertEqual(week.end, midnight(date(2026, 11, 9)))

        month = resolve_period("", "", "", today=date(2026, 3, 15))
        self.assertEqual(month.key, "mes")
        self.assertEqual(month.start, midnight(date(2026, 3, 1)))
        self.assertEqual(month.end, midnight(date(2026, 4, 1)))

        previous = resolve_period("mes_anterior", "", "", today=date(2026, 3, 15))
        self.assertEqual(previous.start, midnight(date(2026, 2, 1)))
        self.assertEqual(previous.end, midnight(date(2026, 3, 1)))

        year = resolve_period("ano", "", "", today=date(2026, 3, 15))
        self.assertEqual(year.start, midnight(date(2026, 1, 1)))
        self.assertEqual(year.end, midnight(date(2027, 1, 1)))

        unknown = resolve_period("foo", "2026-01-01", "2026-01-05", today=sunday)
        self.assertEqual(unknown.key, "mes")
        self.assertEqual(unknown.start, midnight(date(2026, 11, 1)))
        self.assertEqual(unknown.desde, "2026-01-01")

    def test_grouping_switches_after_31_inclusive_days(self):
        january = resolve_period("mes", "", "", today=date(2026, 1, 10))
        february = resolve_period("mes", "", "", today=date(2026, 2, 10))
        year = resolve_period("ano", "", "", today=date(2026, 6, 1))
        self.assertEqual(inclusive_days(january.start, january.end), 31)
        self.assertFalse(uses_monthly(january.start, january.end))
        self.assertEqual(inclusive_days(february.start, february.end), 28)
        self.assertFalse(uses_monthly(february.start, february.end))
        self.assertTrue(uses_monthly(year.start, year.end))

        custom = resolve_period("personalizado", "2026-01-01", "2026-02-01")
        self.assertEqual(custom.error, "")
        self.assertEqual(custom.start, midnight(date(2026, 1, 1)))
        self.assertEqual(custom.end, midnight(date(2026, 2, 2)))
        self.assertEqual(inclusive_days(custom.start, custom.end), 32)
        self.assertTrue(uses_monthly(custom.start, custom.end))

    def test_custom_range_is_validated(self):
        missing = resolve_period("personalizado", "", "2026-03-01")
        invalid = resolve_period("personalizado", "2026-02-31", "2026-03-01")
        inverted = resolve_period("personalizado", "2026-03-10", "2026-03-01")
        same_day = resolve_period("personalizado", "2026-03-10", "2026-03-10")

        self.assertEqual(missing.error, ERROR_MISSING)
        self.assertIsNone(missing.start)
        self.assertEqual(invalid.error, ERROR_INVALID)
        self.assertEqual(inverted.error, ERROR_RANGE)
        self.assertEqual(same_day.end, midnight(date(2026, 3, 11)))


class DashboardQueryTests(TestCase):
    def setUp(self):
        self.client_record = make_client()
        self.other_client = make_client(first_name="Beatriz", last_name="Diaz")
        self.professional = make_professional()
        self.service = make_service()
        self.start = midnight(date(2026, 3, 1))
        self.end = midnight(date(2026, 4, 1))

    def test_kpis_count_distinct_clients_and_include_the_extra_charge(self):
        pedicure = make_service(code="PED-001", name="Pedicura", price_gs=90000)
        first = make_attention(
            self.client_record,
            self.professional,
            at(2026, 3, 2),
            additional_charge_gs=15000,
        )
        PerformedServiceItem.objects.create(
            performed_service=first,
            service=self.service,
            unit_price_gs=70000,
            quantity=1,
        )
        PerformedServiceItem.objects.create(
            performed_service=first,
            service=pedicure,
            unit_price_gs=90000,
            quantity=2,
        )
        second = make_attention(self.client_record, self.professional, at(2026, 3, 3))
        PerformedServiceItem.objects.create(
            performed_service=second,
            service=self.service,
            unit_price_gs=10000,
            quantity=1,
        )
        third = make_attention(self.other_client, self.professional, at(2026, 3, 4))
        PerformedServiceItem.objects.create(
            performed_service=third,
            service=self.service,
            unit_price_gs=20000,
            quantity=1,
        )
        make_attention(self.other_client, self.professional, at(2026, 4, 1))

        kpis = attention_kpis(self.start, self.end)

        self.assertEqual(kpis["value"], 70000 + 180000 + 15000 + 10000 + 20000)
        self.assertEqual(kpis["count"], 3)
        self.assertEqual(kpis["clients"], 2)
        self.assertEqual(kpis["ticket"], 98333)

    def test_empty_period_has_zero_kpis_and_no_ticket(self):
        kpis = attention_kpis(self.start, self.end)

        self.assertEqual(kpis["value"], 0)
        self.assertEqual(kpis["count"], 0)
        self.assertEqual(kpis["clients"], 0)
        self.assertIsNone(kpis["ticket"])

    def test_bounds_include_the_start_and_exclude_the_end(self):
        make_attention(self.client_record, self.professional, self.start, additional_charge_gs=1000)
        make_attention(self.client_record, self.professional, self.end, additional_charge_gs=9000)

        kpis = attention_kpis(self.start, self.end)

        self.assertEqual(kpis["count"], 1)
        self.assertEqual(kpis["value"], 1000)

    def test_ticket_rounds_half_up(self):
        make_attention(self.client_record, self.professional, at(2026, 3, 2), additional_charge_gs=1)
        make_attention(self.other_client, self.professional, at(2026, 3, 3), additional_charge_gs=2)

        self.assertEqual(attention_kpis(self.start, self.end)["ticket"], 2)

    def test_evolution_fills_empty_days_and_groups_longer_ranges_by_month(self):
        make_attention(self.client_record, self.professional, at(2026, 3, 1), additional_charge_gs=1000)
        make_attention(self.client_record, self.professional, at(2026, 3, 3), additional_charge_gs=3000)
        daily = evolution_chart(midnight(date(2026, 3, 1)), midnight(date(2026, 3, 4)))

        self.assertFalse(daily["monthly"])
        self.assertEqual(daily["values"], [1000, 0, 3000])
        self.assertEqual(daily["fullLabels"], ["1/3/2026", "2/3/2026", "3/3/2026"])

        make_attention(self.client_record, self.professional, at(2026, 1, 15), additional_charge_gs=4000)
        monthly = evolution_chart(midnight(date(2026, 1, 1)), midnight(date(2026, 2, 2)))

        self.assertTrue(monthly["monthly"])
        self.assertEqual(monthly["labels"], ["ene 2026", "feb 2026"])
        self.assertEqual(monthly["fullLabels"], ["enero 2026", "febrero 2026"])
        self.assertEqual(monthly["values"], [4000, 0])
        self.assertIsNone(evolution_chart(midnight(date(2026, 5, 1)), midnight(date(2026, 5, 3))))

    def test_top_services_sum_quantity_and_keep_inactive_names(self):
        retired = make_service(code="RET-001", name="Alfa", price_gs=1000, is_active=False)
        beta = make_service(code="BET-001", name="Beta", price_gs=1000)
        tied_later = make_service(code="ZZZ-001", name="Beta", price_gs=1000)
        small = make_service(code="SM-001", name="Chico", price_gs=1000)
        extras = [
            make_service(code=f"X-{index}", name=f"Extra {index}", price_gs=1000)
            for index in range(3)
        ]
        attention = make_attention(
            self.client_record,
            self.professional,
            at(2026, 3, 2),
            additional_charge_gs=50000,
        )
        PerformedServiceItem.objects.create(
            performed_service=attention,
            service=retired,
            unit_price_gs=1000,
            quantity=2,
        )
        PerformedServiceItem.objects.create(
            performed_service=attention,
            service=beta,
            unit_price_gs=1000,
            quantity=2,
        )
        second = make_attention(self.client_record, self.professional, at(2026, 3, 3))
        PerformedServiceItem.objects.create(
            performed_service=second,
            service=tied_later,
            unit_price_gs=1000,
            quantity=2,
        )
        PerformedServiceItem.objects.create(
            performed_service=second,
            service=small,
            unit_price_gs=1000,
            quantity=1,
        )
        for service in extras:
            PerformedServiceItem.objects.create(
                performed_service=second,
                service=service,
                unit_price_gs=1000,
                quantity=1,
            )

        chart = top_services(self.start, self.end)

        self.assertEqual(
            chart["labels"],
            ["Alfa", "Beta", "Beta", "Chico", "Extra 0"],
        )
        self.assertEqual(chart["values"], [2, 2, 2, 1, 1])
        self.assertEqual(attention_kpis(self.start, self.end)["value"], 60000)
        self.assertNotIn("cargo", " ".join(chart["labels"]).lower())

    def test_split_uses_reservation_presence_not_reservation_status(self):
        reservation = Reservation.objects.create(
            client=self.client_record,
            scheduled_at=at(2026, 5, 20),
            status=StatusChoices.CANCELLED,
        )
        make_attention(
            self.client_record,
            self.professional,
            at(2026, 3, 2),
            reservation=reservation,
        )
        make_attention(self.other_client, self.professional, at(2026, 3, 3))
        make_attention(self.other_client, self.professional, at(2026, 3, 4))

        chart = reservation_split(self.start, self.end)

        self.assertEqual(chart["values"], [1, 2])
        self.assertEqual(chart["percents"], ["33,3", "66,7"])
        self.assertIsNone(reservation_statuses(self.start, self.end))
        self.assertIsNone(reservation_split(midnight(date(2026, 8, 1)), midnight(date(2026, 9, 1))))

    def test_reservation_statuses_follow_scheduled_at_and_defined_choices(self):
        Reservation.objects.create(
            client=self.client_record,
            scheduled_at=self.start,
            status=StatusChoices.CONFIRMED,
        )
        Reservation.objects.create(
            client=self.other_client,
            scheduled_at=self.end,
            status=StatusChoices.PENDING,
        )
        make_attention(self.client_record, self.professional, at(2026, 3, 2))

        chart = reservation_statuses(self.start, self.end)

        self.assertEqual(
            chart["labels"],
            ["Pendiente", "Confirmada", "Atendida", "Cancelada", "Ausente"],
        )
        self.assertEqual(chart["values"], [0, 1, 0, 0, 0])
        self.assertEqual(len(chart["colors"]), 5)

    def test_recent_attentions_keep_ten_and_prefetch_relations(self):
        first = make_client(first_name="Nora", last_name="Excluida")
        moment = at(2026, 3, 10, 9, 0)
        make_attention(first, self.professional, moment)
        for index in range(10):
            make_attention(
                self.client_record,
                self.professional,
                moment,
                additional_charge_gs=index + 1,
            )
        newer = make_attention(
            self.other_client,
            self.professional,
            at(2026, 3, 11),
            additional_charge_gs=80,
        )
        PerformedServiceItem.objects.create(
            performed_service=newer,
            service=self.service,
            unit_price_gs=1000,
            quantity=2,
        )

        with self.assertNumQueries(2):
            rows = recent_attentions(self.start, self.end)
            summaries = [row.service_summary for row in rows]
            names = [str(row.client) for row in rows]
            professionals = [str(row.professional) for row in rows]

        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0].pk, newer.pk)
        self.assertEqual(summaries[0], "Manicura × 2")
        self.assertNotIn("Excluida, Nora", names)
        self.assertEqual(professionals[0], "Benitez, Lucia")
        self.assertEqual(len({row.pk for row in rows}), 10)


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("visitante", password="clave-segura")
        self.client.force_login(self.user)
        self.client_record = make_client()
        self.professional = make_professional()

    def test_anonymous_user_goes_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("inicio"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
        self.assertIn("next=/", response.url)

    def test_dashboard_is_the_first_nav_item_and_this_month_is_the_default(self):
        response = self.client.get(reverse("inicio"))
        html = response.content.decode()
        titles = re.findall(r'nav-link-title">([^<]+)', html)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(titles[0], "Dashboard")
        self.assertEqual(response.context["periodo"], "mes")
        self.assertContains(response, "Resumen de actividad del spa")
        self.assertContains(response, "Valor de atenciones")
        self.assertNotContains(response, "Ingresos")
        self.assertContains(response, "Gs. 0")
        self.assertContains(response, "—")
        self.assertContains(response, "Sin datos para el período seleccionado")
        self.assertContains(response, "No se registraron atenciones en este período")
        self.assertContains(response, reverse("atenciones:lista"))
        self.assertContains(response, 'aria-current="page"')

    def test_custom_period_filters_performed_services_and_rejects_an_inverted_range(self):
        included = make_attention(
            self.client_record,
            self.professional,
            at(2026, 3, 10, 8, 0),
            additional_charge_gs=4850000,
        )
        outside = make_attention(
            self.client_record,
            self.professional,
            at(2026, 3, 11, 8, 0),
            additional_charge_gs=111,
        )

        response = self.client.get(
            reverse("inicio"),
            {"periodo": "personalizado", "desde": "2026-03-10", "hasta": "2026-03-10"},
        )

        self.assertContains(response, "Gs. 4.850.000")
        self.assertNotContains(response, "Gs. 111")
        self.assertContains(response, reverse("atenciones:detalle", kwargs={"pk": included.pk}))
        self.assertNotContains(response, reverse("atenciones:detalle", kwargs={"pk": outside.pk}))
        self.assertEqual(response.context["kpis"]["count"], 1)

        invalid = self.client.get(
            reverse("inicio"),
            {"periodo": "personalizado", "desde": "2026-03-12", "hasta": "2026-03-10"},
        )

        self.assertContains(invalid, ERROR_RANGE)
        self.assertIsNone(invalid.context["kpis"])
        self.assertNotContains(invalid, "Gs. 4.850.000")

    def test_post_is_not_allowed(self):
        response = self.client.post(reverse("inicio"))

        self.assertEqual(response.status_code, 405)

    def test_reservation_chart_is_independent_from_attentions(self):
        Reservation.objects.create(
            client=self.client_record,
            scheduled_at=at(2026, 1, 15),
            status=StatusChoices.ATTENDED,
        )
        response = self.client.get(
            reverse("inicio"),
            {"periodo": "personalizado", "desde": "2026-01-01", "hasta": "2026-01-31"},
        )
        charts = response.context["charts"]

        self.assertIsNone(charts["evolution"])
        self.assertIsNone(charts["split"])
        self.assertEqual(charts["statuses"]["values"], [0, 0, 1, 0, 0])
        self.assertContains(response, "No se registraron atenciones en este período")
        self.assertContains(response, "Estados de las reservas")
        payload = chart_payload(
            midnight(date(2026, 1, 1)),
            midnight(date(2026, 2, 1)),
        )
        self.assertEqual(payload["statuses"]["labels"][2], "Atendida")
