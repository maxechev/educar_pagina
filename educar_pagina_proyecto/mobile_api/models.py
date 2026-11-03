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
