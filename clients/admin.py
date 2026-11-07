from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "last_name",
        "first_name",
        "phone",
        "email",
        "source",
        "is_active",
    )
    search_fields = (
        "first_name",
        "last_name",
        "identification_number",
        "phone",
        "email",
    )
    list_filter = ("source", "is_active")
    autocomplete_fields = ("referred_by",)
    readonly_fields = ("created_at", "updated_at", "marketing_consent_at")
