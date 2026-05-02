from rest_framework.permissions import BasePermission, SAFE_METHODS


def _token_claim(request, claim_name: str) -> str | None:
    user = request.user
    token = getattr(user, "token", None)
    if token is None:
        return None
    claim = token.get(claim_name)
    if isinstance(claim, str) and claim:
        return claim
    return None


def _user_role(request) -> str | None:
    token_role = _token_claim(request, "role")
    if token_role:
        return token_role
    role = getattr(request.user, "role", None)
    if isinstance(role, str) and role:
        return role
    return None


def _is_seller(request) -> bool:
    return _user_role(request) == "seller"


def _is_admin(request) -> bool:
    return _user_role(request) == "admin"


def _username(request) -> str:
    token_username = _token_claim(request, "username")
    if token_username:
        return token_username
    username = getattr(request.user, "username", "")
    if isinstance(username, str) and username:
        return username
    return ""


class SellerWritePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return _is_seller(request) or _is_admin(request)


class ProductOwnerPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if _is_admin(request):
            return True
        return _is_seller(request) and bool(obj.seller_username) and obj.seller_username == _username(request)
