from django.contrib import admin

from .models import Professional


@admin.register(Professional)
class ProfessionalAdmin(admin.ModelAdmin):
    list_display = (
        "last_name",
        "first_name",
        "identification_number",
        "phone",
        "email",
        "is_active",
        "commission",
        "start_date",
    )
    search_fields = (
        "first_name",
        "last_name",
        "identification_number",
        "phone",
        "email",
    )
    list_filter = ("is_active",)
    readonly_fields = ("created_at", "updated_at")
