from typing import Any
from django.contrib.auth.models import UserManager
class customUserManager(UserManager):
    def create_user(self, username: str, email: str | None = ..., password: str | None = ..., **extra_fields: Any) -> Any:
        user=self.model(username=username,email=email,**extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user