"""
Application Configuration for TeamBoard API.

================================================================================
INTERVIEW INSIGHT: AppConfig.ready() AND SIGNAL DISCOVERY
================================================================================
Why import signals in AppConfig.ready()?
1. Lifecycle Guarantee:
   - When Django initializes, it builds the application registry in phases.
   - If signals are imported at module level in `__init__.py` or `models.py`,
     models may not be loaded yet, triggering premature model access and
     `AppRegistryNotReady` exceptions or circular import deadlocks.
2. The ready() hook:
   - Django invokes `ready()` on each installed AppConfig only after all models
     across all applications are fully populated and registered in memory.
   - This ensures safe, idempotent listener registration without side effects.
================================================================================
"""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    verbose_name = 'TeamBoard Core API'

    def ready(self):
        # Implicitly connects @receiver decorators in signals.py
        import api.signals  # noqa: F401
