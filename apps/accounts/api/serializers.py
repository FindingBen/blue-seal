
from rest_framework import serializers
from apps.accounts.models import User

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