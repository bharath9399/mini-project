from django.apps import AppConfig


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        # Reset all profiles to offline on server startup to prevent stale online statuses
        import sys
        # Only run reset if we are running the actual server (avoid running during migrations, test, etc.)
        if any(cmd in sys.argv for cmd in ['runserver', 'daphne', 'gunicorn', 'uwsgi']):
            try:
                from .models import Profile
                Profile.objects.update(is_online=False)
                print("[Presence System] Reset all profiles to offline successfully.")
            except Exception as e:
                print("[Presence System] Skip startup presence reset:", e)

