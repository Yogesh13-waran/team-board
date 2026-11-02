"""
Data Models for TeamBoard API.

================================================================================
INTERVIEW DEEP-DIVE: DATABASE ARCHITECTURE & DJANGO ORM
================================================================================
1. OneToOneField vs ForeignKey(unique=True):
   - In Django ORM, `models.OneToOneField(User, ...)` is conceptually a `ForeignKey`
     with `unique=True` on the database level.
   - The key difference in Python ORM semantics:
     A `ForeignKey` exposes a RelatedManager (`user.company_set`), whereas a
     `OneToOneField` exposes a single object directly (`user.company`), raising
     `RelatedObjectDoesNotExist` if no row exists.
   - `related_name='company'` allows clean, idiomatic reverse lookups from `request.user.company`.

2. on_delete=models.CASCADE:
   - When a parent `User` record is deleted, Django enforces cascading deletion to
     clean up associated `Company` and `QueryLog` records, preventing orphaned rows
     and maintaining relational referential integrity.

3. TextChoices vs CharField Choices:
   - Django 3.0+ introduced `models.TextChoices` (extending Python's `enum.Enum`).
   - Benefits: Type safety, descriptive human-readable labels for admin/UI, and
     prevents hardcoded string typos throughout the codebase (`Company.Role.ADMIN`
     vs `'admin'`).

4. API Key Security & Storage:
   - Generated via Python's cryptographically secure pseudo-random number generator
     (`secrets.token_urlsafe(32)`).
   - Generates 32 bytes of secure entropy, base64url-encoded into ~43 characters,
     well within the 64-character limit.
   - `unique=True` enforces a unique B-Tree index in PostgreSQL, ensuring O(log N)
     lookups and preventing key collisions.

5. QueryLog as Source of Truth:
   - Implements immutable append-only event logging for API usage metering and billing.
   - Every search query creates a new row, enabling analytical aggregation
     (`aggregate()`, `annotate()`, `Count()`) across time and companies.
================================================================================
"""

from django.db import models
from django.contrib.auth.models import User


class Company(models.Model):
    """
    Represents a B2B customer (a tenant company) that has registered on TeamBoard.
    Linked to Django's built-in User model via a OneToOneField.
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        CLIENT = 'client', 'Client'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='company',
        help_text="Underlying Django auth user credentials associated with this company."
    )
    company_name = models.CharField(
        max_length=255,
        help_text="Human-readable legal or registered name of the customer company."
    )
    api_key = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        help_text="Cryptographically secure 32-byte urlsafe token issued to the company."
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CLIENT,
        help_text="Access control role: 'admin' for platform staff, 'client' for customer tenants."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the company account was registered."
    )

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_name} ({self.role})"


class KBEntry(models.Model):
    """
    Knowledge Base Entry.
    Represents a curated Q&A record in the knowledge base pre-populated by the platform.
    """

    class Category(models.TextChoices):
        API = 'api', 'API'
        DATABASE = 'database', 'Database'
        CLOUD = 'cloud', 'Cloud'
        FRAMEWORK = 'framework', 'Framework'
        GENERAL = 'general', 'General'

    question = models.TextField(
        help_text="The technical question or prompt."
    )
    answer = models.TextField(
        help_text="Comprehensive and accurate technical answer or explanation."
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        help_text="Technical domain/category of the knowledge base entry."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the entry was authored."
    )

    class Meta:
        verbose_name = "Knowledge Base Entry"
        verbose_name_plural = "Knowledge Base Entries"
        ordering = ['-created_at']

    def __str__(self):
        return self.question[:80]


class QueryLog(models.Model):
    """
    Usage Tracking Log.
    Written every time a company queries the knowledge base.
    Serves as the immutable source of truth for platform analytics and usage-based billing.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='query_logs',
        help_text="The tenant company that initiated this search query."
    )
    search_term = models.CharField(
        max_length=255,
        help_text="Raw search keyword/phrase sent by the client."
    )
    results_count = models.IntegerField(
        help_text="Number of knowledge base entries that matched this query."
    )
    queried_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the query was executed."
    )

    class Meta:
        verbose_name = "Query Log"
        verbose_name_plural = "Query Logs"
        ordering = ['-queried_at']

    def __str__(self):
        return f"{self.company.company_name} - '{self.search_term}' ({self.results_count} results)"
