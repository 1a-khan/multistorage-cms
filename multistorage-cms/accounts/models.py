from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    timezone = models.CharField(max_length=64, default='UTC')
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: list[str] = []

    def __str__(self) -> str:
        return self.email
