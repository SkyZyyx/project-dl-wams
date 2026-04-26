from django.contrib.auth.models import User
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    SELLER = "seller", "Seller"
    CLIENT = "client", "Client"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=16, choices=UserRole.choices, default=UserRole.CLIENT)

    def __str__(self):
        return f"{self.user.username}:{self.role}"
