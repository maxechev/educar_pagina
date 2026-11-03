from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from core.models import Usuario

from .tokens import decode_access_token


class MobileTokenAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if len(parts) != 2 or parts[0].lower() != self.keyword:
            raise AuthenticationFailed("Use Authorization: Bearer <token>.")
        try:
            token = parts[1].decode("ascii")
            claims = decode_access_token(token)
            user = Usuario.objects.get(pk=int(claims["user_id"]))
        except (UnicodeDecodeError, ValueError, Usuario.DoesNotExist) as exc:
            raise AuthenticationFailed("La sesión venció o ya se cerró.") from exc

        if (user.estado or "").casefold() != "activo":
            raise AuthenticationFailed("La cuenta está inactiva.")
        from .services import mobile_role_for_user

        if mobile_role_for_user(user) != claims["role"]:
            raise AuthenticationFailed("El rol de esta cuenta cambió.")
        return user, claims

    def authenticate_header(self, request):
        return "Bearer"
