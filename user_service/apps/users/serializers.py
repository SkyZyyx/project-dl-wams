from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import UserProfile, UserRole


def _resolve_user_role(user: User) -> str:
    if user.is_superuser or user.is_staff:
        return UserRole.ADMIN
    profile = getattr(user, "profile", None)
    if profile and profile.role:
        return profile.role
    return UserRole.CLIENT


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(
        choices=((UserRole.CLIENT, "Client"), (UserRole.SELLER, "Seller")),
        required=False,
        default=UserRole.CLIENT,
        write_only=True,
    )

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name", "role")

    def create(self, validated_data):
        role = validated_data.pop("role", UserRole.CLIENT)
        user = User.objects.create_user(**validated_data, is_staff=False, is_superuser=False)
        UserProfile.objects.create(user=user, role=role)
        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["role"] = _resolve_user_role(instance)
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "role")

    def get_role(self, obj):
        return _resolve_user_role(obj)


class RoleAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = _resolve_user_role(user)
        token["username"] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["role"] = _resolve_user_role(self.user)
        data["username"] = self.user.username
        return data
