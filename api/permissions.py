"""
Custom DRF Permissions for TeamBoard API.

================================================================================
INTERVIEW DEEP-DIVE: DRF PERMISSION ARCHITECTURE & RBAC
================================================================================
1. DRF Permission Execution Pipeline:
   - When an incoming HTTP request hits an APIView:
     1. `initial()` is called by DRF.
     2. `perform_authentication(request)` runs first, populating `request.user`
        and `request.auth` using `DEFAULT_AUTHENTICATION_CLASSES`.
     3. `check_permissions(request)` loops through `permission_classes`.
        Calls `permission.has_permission(request, self)` for each.
     4. If ANY permission returns False, DRF raises:
        - `AuthenticationFailed` (HTTP 401) if `request.user` is anonymous / unauthenticated.
        - `PermissionDenied` (HTTP 403) if `request.user` is authenticated but lacks access.
     5. For detail views with `get_object()`, DRF additionally executes
        `check_object_permissions(request, obj)`.

2. Role-Based Access Control (RBAC):
   - Rather than relying on Django's generic `is_staff` or `is_superuser` flags,
     multi-tenant B2B architectures tie roles directly to the tenant's domain profile
     (`Company.Role.ADMIN` vs `Company.Role.CLIENT`).
   - This ensures strict isolation between platform operators and customer tenants.

3. Why extend `BasePermission`?
   - `BasePermission` defines default `has_permission` and `has_object_permission`
     implementations returning `True`.
   - Overriding `has_permission` provides centralized, reusable, declarative authorization
     across views without repeating if-else statements inside view handlers.
================================================================================
"""

from rest_framework.permissions import BasePermission
from .models import Company


class IsAdminUser(BasePermission):
    """
    Custom permission to restrict access exclusively to users whose associated
    Company has the ADMIN role (Company.Role.ADMIN).

    Requirements:
    - Extends BasePermission.
    - Overrides has_permission().
    - Checks request.user.company.role == Company.Role.ADMIN.
    - Does NOT use is_staff or is_superuser.
    - Unauthenticated requests receive 401 (via DRF's authentication check).
    - Authenticated non-admin CLIENT requests receive 403 Forbidden.
    """

    message = "Access restricted: Platform Administrator privileges required."

    def has_permission(self, request, view):
        # 1. User must be authenticated
        if not (request.user and request.user.is_authenticated):
            return False

        # 2. User must have an associated Company profile
        if not hasattr(request.user, 'company'):
            return False

        # 3. Company role must explicitly be ADMIN (never use is_staff / is_superuser)
        return request.user.company.role == Company.Role.ADMIN
