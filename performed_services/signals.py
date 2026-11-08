from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import PerformedService, PerformedServiceItem


def sync_total(performed_service_id):
    if not performed_service_id:
        return
    try:
        performed = PerformedService.objects.get(pk=performed_service_id)
    except PerformedService.DoesNotExist:
        return
    performed.recalculate_total()
    PerformedService.objects.filter(pk=performed.pk).update(
        total_price_gs=performed.total_price_gs,
        updated_at=timezone.now(),
    )


@receiver(post_save, sender=PerformedServiceItem)
@receiver(post_delete, sender=PerformedServiceItem)
def refresh_performed_service_total(sender, instance, **kwargs):
    sync_total(instance.performed_service_id)
