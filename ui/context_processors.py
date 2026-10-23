from django.conf import settings


def frontend(request):
    return {
        "ui_demo_enabled": settings.DEBUG,
    }
