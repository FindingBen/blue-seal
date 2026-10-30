from django.db import models
import uuid


class ClassPackage(models.Model):
    package_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_package_id = models.CharField(max_length=255, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    class_count = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=False)
    currency = models.CharField(max_length=10, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.name)

class PaymentOrder(models.Model):
    class Provider(models.TextChoices):
        STANDARD = 'standard', 'Standard'
        STRIPE = 'stripe', 'Stripe'

    class PurchaseKind(models.TextChoices):
        ONE_TIME = 'one_time', 'One Time'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        SETTLED = 'settled', 'Settled'
        DECLINED = 'declined', 'Declined'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='payment_orders',
    )
    package = models.ForeignKey(
        'payments.ClassPackage',
        on_delete=models.PROTECT,
        related_name='payment_orders',
    )
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.STANDARD,
    )
    purchase_kind = models.CharField(
        max_length=20,
        choices=PurchaseKind.choices,
        default=PurchaseKind.ONE_TIME,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    provider_charge_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    confirmation_url = models.URLField(max_length=1000, blank=True)
    return_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    price_snapshot = models.JSONField(default=dict, blank=True)
    credits_snapshot = models.JSONField(default=dict, blank=True)
    plan_snapshot = models.JSONField(default=dict, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

class WebhookEvent(models.Model):
    topic = models.CharField(max_length=100)
    external_event_id = models.CharField(max_length=255, blank=True)
    payload_hash = models.CharField(max_length=64, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['topic', 'external_event_id'],
                condition=~models.Q(external_event_id=''),
                name='payment_unique_webhook_external_event',
            ),
        ]
        indexes = [
            models.Index(fields=['topic']),
            models.Index(fields=['processed_at']),
        ]