from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from apps.users.models import UserProfile, UserRole


DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
DEFAULT_EMAIL = "admin@test.com"


def _seed_admin(*, username: str, password: str, email: str):
    user_model = get_user_model()
    user, _ = user_model.objects.get_or_create(
        username=username,
        defaults={"email": email, "is_staff": True, "is_superuser": False, "is_active": True},
    )

    changed_fields: list[str] = []
    if user.email != email:
        user.email = email
        changed_fields.append("email")
    if not user.is_staff:
        user.is_staff = True
        changed_fields.append("is_staff")
    if user.is_superuser:
        user.is_superuser = False
        changed_fields.append("is_superuser")
    if not user.is_active:
        user.is_active = True
        changed_fields.append("is_active")
    if not user.check_password(password):
        user.set_password(password)
        changed_fields.append("password")

    non_password_fields = [field for field in changed_fields if field != "password"]
    if non_password_fields:
        user.save(update_fields=non_password_fields)
    if "password" in changed_fields:
        user.save(update_fields=["password"])

    UserProfile.objects.update_or_create(user=user, defaults={"role": UserRole.ADMIN})
    return user, bool(changed_fields)


class Command(BaseCommand):
    help = "Seed a local demo admin user for the main app login."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.getenv("DEMO_ADMIN_USERNAME", DEFAULT_USERNAME))
        parser.add_argument("--password", default=os.getenv("DEMO_ADMIN_PASSWORD", DEFAULT_PASSWORD))
        parser.add_argument("--email", default=os.getenv("DEMO_ADMIN_EMAIL", DEFAULT_EMAIL))

    def handle(self, *args, **options):
        user, changed = _seed_admin(
            username=options["username"],
            password=options["password"],
            email=options["email"],
        )
        action = "Updated" if changed else "Already present"
        self.stdout.write(self.style.SUCCESS(f"{action} demo login user {user.username} <{user.email}>."))
