from django.apps import AppConfig


class TestsManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tests_manager'
    verbose_name = 'Test Suite Manager'
