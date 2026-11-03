from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import MobileSession

TOKEN_TTL_SECONDS = 8 * 60 * 60


class InvalidToken(ValueError):
    pass


def create_access_token(user_id, role):
    token = AccessToken()
    token["user_id"] = user_id
    token["role"] = role
    token["iss"] = "educar-mobile"
    expires_at = datetime.fromtimestamp(int(token["exp"]), tz=datetime_timezone.utc)
    MobileSession.objects.create(
        jti=token["jti"],
        user_id=user_id,
        role=role,
        expires_at=expires_at,
    )
    return str(token)


def decode_access_token(token_string):
    try:
        token = AccessToken(token_string)
        payload = token.payload
        user_id = int(payload["user_id"])
        role = payload["role"]
        jti = payload["jti"]
        if role not in {"padre", "administrativo"} or not isinstance(jti, str):
            raise InvalidToken("Invalid claims")
        session = MobileSession.objects.filter(
            jti=jti,
            user_id=user_id,
            role=role,
            expires_at__gt=timezone.now(),
            revoked_at__isnull=True,
        ).first()
        if session is None:
            raise InvalidToken("Session is no longer active")
        return payload
    except InvalidToken:
        raise
    except (TokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidToken("Malformed or expired token") from exc
