from rest_framework.permissions import BasePermission, SAFE_METHODS


def _token_claim(request, claim_name: str) -> str | None:
    user = request.user
    token = getattr(user, "token", None)
    if token is None:
        return None
    claim_value = token.get(claim_name)
    if isinstance(claim_value, str) and claim_value:
        return claim_value
    return None


def _user_role(request) -> str | None:
    user = request.user
    role = getattr(user, "role", None)
    if isinstance(role, str) and role:
        return role
    return _token_claim(request, "role")


def _is_admin(request) -> bool:
    return _user_role(request) == "admin"


def _is_seller(request) -> bool:
    return _user_role(request) == "seller"


class SellerOrAdminWritePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return _is_admin(request) or _is_seller(request)
