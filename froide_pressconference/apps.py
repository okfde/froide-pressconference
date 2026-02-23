from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FroidePressconferenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "froide_pressconference"
    verbose_name = _("Press Conferences")

    def ready(self):
        from froide.foirequest.models import FoiRequest

        from .listeners import create_link

        FoiRequest.request_sent.connect(create_link)
