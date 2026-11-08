from django.contrib import admin

from .models import PerformedService, PerformedServiceItem


class PerformedServiceItemInline(admin.TabularInline):
    model = PerformedServiceItem
    extra = 0


@admin.register(PerformedService)
class PerformedServiceAdmin(admin.ModelAdmin):
    list_display = (
        "performed_at",
        "client",
        "professional",
        "total_price_gs",
        "reservation",
    )
    list_select_related = ("client", "professional", "reservation")
    search_fields = (
        "client__first_name",
        "client__last_name",
        "professional__first_name",
        "professional__last_name",
    )
    readonly_fields = ("total_price_gs", "created_at", "updated_at")
    inlines = [PerformedServiceItemInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalculate_total()
        form.instance.save(update_fields=["total_price_gs", "updated_at"])
