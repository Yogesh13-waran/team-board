"""
Root URL Configuration for TeamBoard Project.

Directs incoming URL patterns to the appropriate domain applications.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]
