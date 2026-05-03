from django.apps import AppConfig

class ApilusConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'APilus'

    def ready(self):
        # We import inside the function to avoid 'Apps aren't loaded yet' errors
        from .llm import get_vector_db
        import os

        # This prevents the double-loading bug when using the auto-reloader
        if os.environ.get('RUN_MAIN') == 'true':
            print("🚀 Warm-up: Initializing Vector Database...")
            get_vector_db()