import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.service import WalletTransactionService
from apps.payments.models import ClassPackage, PaymentOrder, WebhookEvent

logger = logging.getLogger(__name__)


class PaymentOrderService:
    @staticmethod
    def list_active_packages():
        return ClassPackage.objects.filter(is_active=True).order_by("class_count")

    @staticmethod
    def create_checkout_session(*, user, package_id):
        package = ClassPackage.objects.filter(
            package_id=package_id,
            is_active=True,
        ).first()
        if package is None:
            raise ValidationError("The selected class package is unavailable.")
        if package.class_count <= 0 or user.price_per_class <= 0:
            raise ValidationError("The selected class package has invalid pricing.")
        if len(package.currency) != 3 or not package.currency.isalpha():
            raise ValidationError("The selected class package has an invalid currency.")

        total_price = Decimal(user.price_per_class) * package.class_count
        order = PaymentOrder.objects.create(
            user=user,
            package=package,
            provider=PaymentOrder.Provider.STRIPE,
            purchase_kind=PaymentOrder.PurchaseKind.ONE_TIME,
            status=PaymentOrder.Status.PENDING,
            price_snapshot={
                "amount": str(total_price),
                "currency_code": package.currency.lower(),
            },
            credits_snapshot={
                "amount": package.class_count,
                "unit": "classes",
            },
        )

        success_url = (
            settings.DOMAIN_STRIPE_PURCHASE_NAME
            or f"{settings.FRONTEND_URL.rstrip('/')}/payment/success"
        )
        cancel_url = (
            settings.DOMAIN_STRIPE_NAME_CANCEL
            or f"{settings.FRONTEND_URL.rstrip('/')}/payment/cancel"
        )

        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            customer_details = (
                {"customer": user.stripe_customer_id}
                if user.stripe_customer_id
                else {"customer_email": user.email}
            )
            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": package.currency.lower(),
                            "unit_amount": int(total_price * Decimal("100")),
                            "product_data": {"name": package.name},
                        },
                        "quantity": 1,
                    }
                ],
                **customer_details,
                client_reference_id=str(user.pk),
                metadata={
                    "payment_order_id": str(order.pk),
                    "user_id": str(user.pk),
                    "class_count": str(package.class_count),
                },
                success_url=(
                    f"{success_url}{'&' if '?' in success_url else '?'}"
                    "success=true&session_id={CHECKOUT_SESSION_ID}"
                ),
                cancel_url=(
                    f"{cancel_url}{'&' if '?' in cancel_url else '?'}cancel=true"
                ),
            )
        except Exception as exc:
            order.status = PaymentOrder.Status.FAILED
            order.failure_reason = str(exc)
            order.save(update_fields=["status", "failure_reason", "updated_at"])
            logger.exception("Could not create Stripe Checkout Session for order %s", order.pk)
            raise

        order.provider_charge_id = session.id
        order.confirmation_url = session.url
        order.save(
            update_fields=["provider_charge_id", "confirmation_url", "updated_at"]
        )
        return {"url": session.url, "order_id": str(order.pk)}

    @staticmethod
    @transaction.atomic
    def handle_stripe_webhook(*, event, payload, payload_hash):
        event_type = event.get("type", "")
        event_id = event.get("id", "")
        webhook_event, created = WebhookEvent.objects.get_or_create(
            topic=event_type,
            external_event_id=event_id,
            defaults={
                "payload_hash": payload_hash,
                "payload": payload,
            },
        )
        if not created and webhook_event.processed_at is not None:
            return webhook_event.processing_result or {"status": "duplicate"}

        if event_type not in {
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
            "checkout.session.async_payment_failed",
            "checkout.session.expired",
        }:
            return PaymentOrderService._finalize_webhook(
                webhook_event,
                {"status": "ignored", "event_type": event_type},
            )

        checkout = event.get("data", {}).get("object", {})
        if checkout.get("mode") != "payment":
            return PaymentOrderService._finalize_webhook(
                webhook_event, {"status": "ignored", "reason": "Not a one-time payment."}
            )

        order = PaymentOrderService._get_order_for_checkout(checkout)
        failure_statuses = {
            "checkout.session.async_payment_failed": (
                PaymentOrder.Status.FAILED,
                "Stripe reported that the asynchronous payment failed.",
            ),
            "checkout.session.expired": (
                PaymentOrder.Status.CANCELLED,
                "Stripe Checkout Session expired before payment.",
            ),
        }
        if event_type in failure_statuses:
            if order.status == PaymentOrder.Status.SETTLED:
                return PaymentOrderService._finalize_webhook(
                    webhook_event,
                    {"status": "already_settled", "payment_order_id": str(order.pk)},
                )
            order.status, order.failure_reason = failure_statuses[event_type]
            order.save(update_fields=["status", "failure_reason", "updated_at"])
            return PaymentOrderService._finalize_webhook(
                webhook_event,
                {
                    "status": order.status,
                    "payment_order_id": str(order.pk),
                },
            )

        if checkout.get("payment_status") != "paid":
            return PaymentOrderService._finalize_webhook(
                webhook_event, {"status": "pending", "reason": "Payment is not paid."}
            )

        session_id = checkout["id"]
        expected_amount = int(
            Decimal(order.price_snapshot["amount"]) * Decimal("100")
        )
        if (
            checkout.get("amount_total") != expected_amount
            or checkout.get("currency", "").lower()
            != order.price_snapshot["currency_code"].lower()
        ):
            raise ValidationError("Stripe payment amount or currency does not match the order.")

        if order.status == PaymentOrder.Status.SETTLED:
            return PaymentOrderService._finalize_webhook(
                webhook_event,
                {"status": "already_settled", "payment_order_id": str(order.pk)},
            )

        class_count = int(order.credits_snapshot["amount"])
        top_up_result = WalletTransactionService.top_up_wallet(
            str(order.user_id),
            class_count,
            payment_refferance={
                "payment_order_id": str(order.pk),
                "provider_charge_id": session_id,
                "note": "Class package purchased through Stripe",
            },
        )
        if top_up_result is not True:
            raise RuntimeError(f"Could not credit wallet for payment order {order.pk}: {top_up_result}")

        now = timezone.now()
        order.provider_charge_id = session_id
        order.status = PaymentOrder.Status.SETTLED
        order.approved_at = order.approved_at or now
        order.settled_at = now
        order.failure_reason = ""
        order.save(
            update_fields=[
                "provider_charge_id",
                "status",
                "approved_at",
                "settled_at",
                "failure_reason",
                "updated_at",
            ]
        )
        return PaymentOrderService._finalize_webhook(
            webhook_event,
            {
                "status": "settled",
                "payment_order_id": str(order.pk),
                "credited_classes": class_count,
            },
        )

    @staticmethod
    def _get_order_for_checkout(checkout):
        order_id = checkout.get("metadata", {}).get("payment_order_id")
        if not order_id:
            raise ValidationError("Stripe Checkout Session has no payment order metadata.")

        try:
            order = PaymentOrder.objects.select_for_update().select_related(
                "package"
            ).get(pk=order_id)
        except (PaymentOrder.DoesNotExist, ValueError) as exc:
            raise ValidationError("No payment order matches the Stripe Checkout Session.") from exc

        session_id = checkout.get("id")
        if not session_id or (
            order.provider_charge_id and order.provider_charge_id != session_id
        ):
            raise ValidationError("Stripe Checkout Session does not match the payment order.")
        return order

    @staticmethod
    def _finalize_webhook(webhook_event, result):
        webhook_event.processing_result = result
        webhook_event.processed_at = timezone.now()
        webhook_event.save(update_fields=["processing_result", "processed_at"])
        return result
