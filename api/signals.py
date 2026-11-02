"""
Signals for TeamBoard API.

================================================================================
INTERVIEW DEEP-DIVE: DJANGO SIGNALS VS MODEL SAVE() OVERRIDE
================================================================================
1. What is the Django Signal Dispatcher?
   - Django includes a signal dispatcher (Observer/Publish-Subscribe pattern)
     allowing decoupled applications to get notified when actions occur elsewhere.
   - Core built-in model signals include:
     * `pre_init` / `post_init`: Sent at start/end of model's __init__() method.
     * `pre_save` / `post_save`: Sent before/after model's save() method is executed.
     * `pre_delete` / `post_delete`: Sent before/after model deletion or queryset delete.
     * `m2m_changed`: Sent when a ManyToManyField is modified.

2. Signal vs overriding `save()` method - When to use which?
   - Overriding `save()`:
     * Best when the logic strictly pertains to the internal state of that specific model
       (e.g., computing a slug from a title before saving).
     * Faster (no signal dispatch overhead) and explicit in control flow.
   - Using `post_save` signals:
     * Essential when extending or reacting to models defined in third-party or built-in
       packages where you cannot directly edit the class code (such as `django.contrib.auth.models.User`).
     * Clean decoupling: `User` model knows nothing about the `Company` profile.
     * Allows multiple independent listeners to attach hooks without subclassing.

3. How `created` and `instance._state.adding` Work Under the Hood:
   - When a Django model instance is first created in memory via `User(...)`, Django sets:
     `instance._state.adding = True` (indicating this object is new and needs a SQL INSERT).
   - In `Model.save_base()`, Django checks `if not self._state.adding:` to run an UPDATE,
     or performs an INSERT and sets `created = True`.
   - Django then fires the `post_save` signal with `created=True`, before resetting
     `instance._state.adding = False`.
   - Therefore, checking `if created:` inside `post_save` reliably indicates that the row
     was newly inserted into the database table.

4. Cryptographically Secure API Key Generation:
   - We use Python's standard library `secrets` module (`secrets.token_urlsafe(32)`).
   - Unlike `random` (which uses a Mersenne Twister and is predictable), `secrets`
     sources entropy directly from the operating system's CSPRNG (e.g. CryptGenRandom
     on Windows, /dev/urandom on Linux/POSIX).
   - 32 bytes of cryptographic entropy equates to 256 bits, preventing brute force
     enumeration attacks.
================================================================================
"""

import secrets
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Company


@receiver(post_save, sender=User)
def create_company_profile(sender, instance, created, **kwargs):
    """
    Auto-creates a Company profile and generates a secure API key
    when a new User instance is created.

    Triggered immediately after User.objects.create_user() or User.save() finishes.
    """
    # Verify that this is a newly inserted User record
    if created:
        # Default company name is set to email (or username fallback)
        # The registration view will update this to the actual requested company_name
        fallback_name = instance.email if instance.email else instance.username
        Company.objects.create(
            user=instance,
            company_name=fallback_name,
            api_key=secrets.token_urlsafe(32),
            role=Company.Role.CLIENT
        )

