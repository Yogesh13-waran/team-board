#!/usr/bin/env python
"""
TeamBoard Management Entry Point.

================================================================================
INTERVIEW PERSPECTIVE: DJANGO ENTRY POINTS & EXECUTION MODEL
================================================================================
1. What does `manage.py` do?
   - It is a thin wrapper around `django.core.management.execute_from_command_line`.
   - Its primary responsibility is setting the `DJANGO_SETTINGS_MODULE` environment variable
     pointing to the project's settings configuration (`teamboard.settings`).
   - Difference between `django-admin` and `manage.py`:
     * `django-admin` is installed globally with Django and requires manually passing
       `--settings` or setting `DJANGO_SETTINGS_MODULE` in the shell.
     * `manage.py` is created per-project and automatically binds that specific project's
       settings and adds the project root to `sys.path`.

2. The Command Execution Lifecycle:
   - `execute_from_command_line(sys.argv)` invokes `ManagementUtility`.
   - It parses arguments, discovers installed management commands across all `INSTALLED_APPS`
     (by looking inside `<app>/management/commands/<command_name>.py`), sets up Django apps
     (`django.setup()`), and invokes the target command's `handle()` method.
================================================================================
"""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teamboard.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
