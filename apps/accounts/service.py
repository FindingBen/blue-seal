
from .models import User, Wallet
from django.db import transaction
class AccountService:


    @staticmethod
    @transaction.atomic
    def register_user(email, password, name, user_type):
        print(email,password,name,user_type)
        """Service model for accounts"""
        user = User.objects.create_user(
            email=email,
            password=password,
            name=name,
            is_active=False,
            user_type=user_type
        )

        Wallet.objects.create(
            user=user
        )

        # verification = EmailVerification.objects.create(user=user)