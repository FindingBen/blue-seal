
from rest_framework import serializers
from apps.accounts.models import InvatationToken, User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone

def build_user_payload(user):

    return {
        "id": str(user.account_id),
        "email": user.email,
        "user_type": user.user_type,
    }

class RegisterSerializer(serializers.Serializer):
    USER_TYPE_CHOICES = ["regular", "shopify"]
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    name = serializers.CharField()
    user_type = user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)
    invitation_token = serializers.UUIDField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value

    def validate_invitation_token(self, value):
        invitation = InvatationToken.objects.filter(token=value).first()
        if (
            invitation is None
            or invitation.is_used
            or invitation.expires_at <= timezone.now()
        ):
            raise serializers.ValidationError(
                "The invitation token is invalid, expired, or already used."
            )
        return value


class TutorSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="account_id", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name"]


class CustomTokenSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        if not user.is_active:
            raise AuthenticationFailed("Email not verified")
        
        data["user"] = build_user_payload(self.user)

        return data