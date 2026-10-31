import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email must be provided")

        email = self.normalize_email(email)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("user_type", "regular")

        if not password:
            raise ValueError("Superuser must have a password")

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    """standard user model"""
    objects = UserManager()

    USER_TYPE_CHOICES = [
        ("regular", "Regular"),
        ("tutor","Tutor"),
        ("shopify", "Shopify"),
    ]
    username = None
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    account_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )

    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

class Wallet(models.Model):
    """Standard Wallet model"""
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="wallet")
    balance = models.IntegerField(default=0)
    reserved = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    updated_at = models.DateTimeField(auto_now=True)

class ClassLedger(models.Model):
    """Standard Ledger model"""
    ENTRY_TYPES = [
        ("top_up", "Top Up"),
        ("reservation", "Reservation"),
        ("debit", "Debit"),
        ("refund", "Refund"),
        ("adjustment", "Adjustment"),
    ]
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="entries")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=4)
    reference_id = models.CharField(max_length=64, blank=True)  # payment_id
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class EmailVerification(models.Model):
    """Standard Verification model"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_tokens")

    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    is_used = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

class InvatationToken(models.Model):
    LIFETIME = timedelta(minutes=20)

    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="created_invitations",
    )
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True)

    @property
    def expires_at(self):
        return self.created_at + self.LIFETIME