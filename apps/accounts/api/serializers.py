
from rest_framework import serializers
from apps.accounts.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed

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
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value

class CustomTokenSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        if not user.is_active:
            raise AuthenticationFailed("Email not verified")
        
        data["user"] = build_user_payload(self.user)

        return data