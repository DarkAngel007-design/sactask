from rest_framework import permissions


class ReadOnlyOrAdmin(permissions.BasePermission):
    """Anyone may read the catalogue; only staff may change it."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)
