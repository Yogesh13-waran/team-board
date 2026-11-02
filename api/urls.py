"""
URL Routing for TeamBoard API.

Maps endpoint URLs to corresponding API views.
"""

from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    KBQueryView,
    AdminUsageSummaryView
)

urlpatterns = [
    # Public Authentication Endpoints
    path('auth/register/', RegisterView.as_view(), name='api-auth-register'),
    path('auth/login/', LoginView.as_view(), name='api-auth-login'),

    # Protected Knowledge Base Search Endpoint
    path('kb/query/', KBQueryView.as_view(), name='api-kb-query'),

    # Admin Usage Statistics Dashboard Endpoint
    path('admin/usage-summary/', AdminUsageSummaryView.as_view(), name='api-admin-usage-summary'),
]

