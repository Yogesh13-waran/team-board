"""
Django Admin Registration for TeamBoard Models.

Provides an intuitive administration interface for platform operators.
"""

from django.contrib import admin
from .models import Company, KBEntry, QueryLog


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'company_name', 'user', 'role', 'api_key', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('company_name', 'user__username', 'user__email', 'api_key')
    readonly_fields = ('api_key', 'created_at')


@admin.register(KBEntry)
class KBEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'question_preview', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('question', 'answer')
    readonly_fields = ('created_at',)

    def question_preview(self, obj):
        return obj.question[:80]
    question_preview.short_description = "Question"


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'search_term', 'results_count', 'queried_at')
    list_filter = ('queried_at', 'company')
    search_fields = ('search_term', 'company__company_name')
    readonly_fields = ('queried_at',)
