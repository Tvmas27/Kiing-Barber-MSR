from django.apps import AppConfig
from django.conf import settings
from .firebase import initialize_firebase

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        initialize_firebase(settings.BASE_DIR.parent)
