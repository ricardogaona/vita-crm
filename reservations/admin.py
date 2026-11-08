from django.contrib import admin

from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("client", "scheduled_at", "status", "attended_at")
    list_filter = ("status",)
    list_select_related = ("client",)
    search_fields = (
        "client__first_name",
        "client__last_name",
        "client__phone",
        "client__identification_number",
        "client__email",
    )
    autocomplete_fields = ("client",)
    readonly_fields = ("attended_at", "created_at", "updated_at")
