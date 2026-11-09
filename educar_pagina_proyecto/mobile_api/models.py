from django.db import models


class MobileSession(models.Model):
    jti = models.CharField(max_length=64, unique=True)
    user_id = models.PositiveIntegerField(db_index=True)
    role = models.CharField(max_length=20)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mobile_api_session"


class MobilePasswordReset(models.Model):
    user = models.ForeignKey(
        "core.Usuario",
        on_delete=models.CASCADE,
        related_name="mobile_password_resets",
    )
    code_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(blank=True, null=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "mobile_api_password_reset"
        indexes = [
            models.Index(
                fields=["user", "used_at"],
                name="mapi_reset_user_used_idx",
            )
        ]
