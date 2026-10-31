import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import ClassLedger, User, Wallet
from apps.payments.models import ClassPackage, PaymentOrder
from apps.payments.service import PaymentOrderService


@override_settings(
    STRIPE_SECRET_KEY="sk_test_placeholder",
    FRONTEND_URL="https://example.test",
    DOMAIN_STRIPE_PURCHASE_NAME=None,
    DOMAIN_STRIPE_NAME_CANCEL=None,
    STRIPE_WEBHOOK_SECRET="whsec_test_placeholder",
)
class StripeClassPackageTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(
            email="student@example.test",
            name="Student",
            user_type="regular",
            password="unused",
        )
        self.wallet = Wallet.objects.create(user=self.user)
        self.package = ClassPackage.objects.create(
            name="Three classes",
            class_count=3,
            price=Decimal("45.00"),
            currency="USD",
            is_active=True,
        )

    def test_packages_endpoint_lists_active_packages(self):
        ClassPackage.objects.create(
            name="Inactive package",
            class_count=1,
            price=Decimal("20.00"),
            is_active=False,
        )
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse("class-packages"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "package_id": str(self.package.pk),
                    "name": "Three classes",
                    "class_count": 3,
                    "price": "45.00",
                    "currency": "USD",
                }
            ],
        )

    @patch("apps.payments.service.stripe.checkout.Session.create")
    def test_checkout_endpoint_returns_url_for_selected_package(self, create_session):
        create_session.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.test/session",
        )
        self.user.price_per_class = 20
        self.user.save(update_fields=["price_per_class"])
        self.client.force_authenticate(self.user)

        response = self.client.post(
            reverse("stripe-checkout"),
            {"package_id": str(self.package.pk)},
            content_type="application/json",
        )

        order = PaymentOrder.objects.get()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["url"], "https://checkout.stripe.test/session")
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.provider, PaymentOrder.Provider.STRIPE)
        self.assertEqual(order.status, PaymentOrder.Status.PENDING)
        self.assertEqual(order.credits_snapshot["amount"], 3)
        self.assertEqual(order.price_snapshot["amount"], "60")
        self.assertEqual(
            create_session.call_args.kwargs["line_items"][0]["price_data"][
                "unit_amount"
            ],
            6000,
        )
        self.assertEqual(order.provider_charge_id, "cs_test_123")
        self.assertNotIn(
            "payment_method_types",
            create_session.call_args.kwargs,
        )
        create_session.assert_called_once()

    @patch("apps.payments.service.stripe.checkout.Session.create")
    def test_checkout_uses_existing_stripe_customer(self, create_session):
        create_session.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.test/session",
        )
        self.user.stripe_customer_id = "cus_test_123"
        self.user.save(update_fields=["stripe_customer_id"])

        PaymentOrderService.create_checkout_session(
            user=self.user,
            package_id=str(self.package.pk),
        )

        self.assertEqual(create_session.call_args.kwargs["customer"], "cus_test_123")
        self.assertNotIn("customer_email", create_session.call_args.kwargs)

    @patch("apps.payments.api.views.stripe.Webhook.construct_event")
    @patch("apps.payments.service.stripe.checkout.Session.create")
    def test_webhook_endpoint_credits_wallet_after_verified_payment(
        self, create_session, construct_event
    ):
        create_session.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.test/session",
        )
        checkout = PaymentOrderService.create_checkout_session(
            user=self.user,
            package_id=str(self.package.pk),
        )
        order = PaymentOrder.objects.get(pk=checkout["order_id"])
        event = {
            "id": "evt_test_endpoint",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "mode": "payment",
                    "payment_status": "paid",
                    "amount_total": 4500,
                    "currency": "usd",
                    "metadata": {"payment_order_id": str(order.pk)},
                }
            },
        }
        construct_event.return_value = event

        response = self.client.post(
            reverse("stripe-webhook"),
            data=json.dumps(event),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        self.wallet.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.wallet.balance, 3)
        self.assertEqual(ClassLedger.objects.filter(wallet=self.wallet).count(), 1)

    @patch("apps.payments.service.stripe.checkout.Session.create")
    def test_paid_webhook_credits_wallet_once(self, create_session):
        create_session.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.test/session",
        )
        checkout = PaymentOrderService.create_checkout_session(
            user=self.user,
            package_id=str(self.package.pk),
        )
        order = PaymentOrder.objects.get(pk=checkout["order_id"])
        event = {
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "mode": "payment",
                    "payment_status": "paid",
                    "amount_total": 4500,
                    "currency": "usd",
                    "metadata": {"payment_order_id": str(order.pk)},
                }
            },
        }

        result = PaymentOrderService.handle_stripe_webhook(
            event=event,
            payload=event,
            payload_hash="a" * 64,
        )
        duplicate_result = PaymentOrderService.handle_stripe_webhook(
            event=event,
            payload=event,
            payload_hash="a" * 64,
        )

        self.wallet.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(result["status"], "settled")
        self.assertEqual(duplicate_result["status"], "settled")
        self.assertEqual(self.wallet.balance, 3)
        self.assertEqual(order.status, PaymentOrder.Status.SETTLED)
        self.assertEqual(ClassLedger.objects.filter(wallet=self.wallet).count(), 1)

    @patch("apps.payments.service.stripe.checkout.Session.create")
    def test_unpaid_checkout_does_not_credit_wallet(self, create_session):
        create_session.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.test/session",
        )
        checkout = PaymentOrderService.create_checkout_session(
            user=self.user,
            package_id=str(self.package.pk),
        )
        order = PaymentOrder.objects.get(pk=checkout["order_id"])
        event = {
            "id": "evt_test_unpaid",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "mode": "payment",
                    "payment_status": "unpaid",
                    "metadata": {"payment_order_id": str(order.pk)},
                }
            },
        }

        result = PaymentOrderService.handle_stripe_webhook(
            event=event,
            payload=event,
            payload_hash="b" * 64,
        )

        self.wallet.refresh_from_db()
        self.assertEqual(result["status"], "pending")
        self.assertEqual(self.wallet.balance, 0)

    @patch("apps.payments.service.stripe.checkout.Session.create")
    def test_expired_checkout_cancels_order_without_crediting_wallet(self, create_session):
        create_session.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.test/session",
        )
        checkout = PaymentOrderService.create_checkout_session(
            user=self.user,
            package_id=str(self.package.pk),
        )
        order = PaymentOrder.objects.get(pk=checkout["order_id"])
        event = {
            "id": "evt_test_expired",
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "mode": "payment",
                    "metadata": {"payment_order_id": str(order.pk)},
                }
            },
        }

        result = PaymentOrderService.handle_stripe_webhook(
            event=event,
            payload=event,
            payload_hash="c" * 64,
        )

        self.wallet.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(result["status"], PaymentOrder.Status.CANCELLED)
        self.assertEqual(order.status, PaymentOrder.Status.CANCELLED)
        self.assertEqual(self.wallet.balance, 0)
