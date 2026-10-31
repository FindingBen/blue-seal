from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.exceptions import WalletDoesNotExistError
from apps.accounts.models import InvatationToken, User, Wallet
from apps.accounts.service import WalletTransactionService
import stripe


class WalletApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="student@example.test",
            password="test-password",
            name="Student",
            user_type="regular",
        )
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance=5,
            reserved=Decimal("2"),
        )
        self.client.force_authenticate(self.user)

    def test_wallet_endpoint_returns_class_counts(self):
        response = self.client.get(reverse("wallet"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "balance": 5,
                "reserved": 2.0,
                "available": 3.0,
                "updated_at": self.wallet.updated_at.isoformat().replace("+00:00", "Z"),
            },
        )

    def test_wallet_service_returns_wallet_for_user(self):
        wallet = WalletTransactionService.get_wallet(self.user.pk)

        self.assertEqual(wallet, self.wallet)

    def test_wallet_endpoint_returns_not_found_if_wallet_missing(self):
        self.wallet.delete()

        response = self.client.get(reverse("wallet"))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "Wallet not found."})

    def test_wallet_service_raises_if_wallet_missing(self):
        self.wallet.delete()

        with self.assertRaises(WalletDoesNotExistError):
            WalletTransactionService.get_wallet(self.user.pk)


class RegisterApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tutor = User.objects.create_user(
            email="tutor@example.test",
            password="Secure-test-password-123",
            name="Tutor",
            user_type="tutor",
        )
        self.invitation = InvatationToken.objects.create(created_by=self.tutor)
        self.registration_data = {
            "email": "jane@example.test",
            "password": "Secure-test-password-123",
            "name": "Jane Doe",
            "user_type": "regular",
            "invitation_token": str(self.invitation.token),
        }

    @patch("apps.accounts.api.views.stripe.Customer.create")
    def test_registration_creates_stripe_customer(self, create_customer):
        create_customer.return_value = SimpleNamespace(id="cus_test_123")

        response = self.client.post(
            "/api/accounts/register/",
            self.registration_data,
            format="json",
        )

        user = User.objects.get(email="jane@example.test")
        self.invitation.refresh_from_db()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(user.stripe_customer_id, "cus_test_123")
        self.assertEqual(user.tutor, self.tutor)
        self.assertTrue(Wallet.objects.filter(user=user).exists())
        self.assertTrue(self.invitation.is_used)
        create_customer.assert_called_once_with(
            name="Jane Doe",
            email="jane@example.test",
            metadata={"account_id": str(user.pk)},
        )

    @patch("apps.accounts.api.views.stripe.Customer.create")
    def test_registration_rolls_back_if_stripe_customer_creation_fails(
        self, create_customer
    ):
        create_customer.side_effect = stripe.StripeError(
            "Stripe customer creation failed."
        )

        with self.assertLogs("apps.accounts.api.views", level="ERROR"):
            response = self.client.post(
                "/api/accounts/register/",
                self.registration_data,
                format="json",
            )

        self.assertEqual(response.status_code, 502)
        self.assertFalse(User.objects.filter(email="jane@example.test").exists())
        self.invitation.refresh_from_db()
        self.assertFalse(self.invitation.is_used)

    def test_registration_requires_invitation_token(self):
        registration_data = self.registration_data.copy()
        registration_data.pop("invitation_token")

        response = self.client.post(
            "/api/accounts/register/",
            registration_data,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("invitation_token", response.json())

    def test_registration_rejects_unknown_invitation(self):
        registration_data = self.registration_data.copy()
        registration_data["invitation_token"] = (
            "3e8ec7fe-8878-4ed8-bacc-9f4abce0dc8b"
        )

        response = self.client.post(
            "/api/accounts/register/",
            registration_data,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="jane@example.test").exists())

    def test_registration_rejects_expired_invitation(self):
        InvatationToken.objects.filter(pk=self.invitation.pk).update(
            created_at=timezone.now() - timedelta(minutes=21)
        )

        response = self.client.post(
            "/api/accounts/register/",
            self.registration_data,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="jane@example.test").exists())

    def test_registration_rejects_used_invitation(self):
        self.invitation.is_used = True
        self.invitation.save(update_fields=["is_used"])

        response = self.client.post(
            "/api/accounts/register/",
            self.registration_data,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="jane@example.test").exists())

    def test_tutor_can_create_invitation_valid_for_twenty_minutes(self):
        self.client.force_authenticate(self.tutor)
        before_request = timezone.now()

        response = self.client.post(reverse("invitation-create"), {}, format="json")

        self.assertEqual(response.status_code, 201)
        invitation = InvatationToken.objects.get(token=response.json()["token"])
        self.assertEqual(invitation.created_by, self.tutor)
        self.assertEqual(
            response.json()["expires_at"],
            (invitation.created_at + timedelta(minutes=20)).isoformat().replace(
                "+00:00", "Z"
            ),
        )
        self.assertGreaterEqual(invitation.created_at, before_request)

    def test_non_tutor_cannot_create_invitation(self):
        student = User.objects.create_user(
            email="student@example.test",
            password="Secure-test-password-123",
            name="Student",
            user_type="regular",
        )
        self.client.force_authenticate(student)

        response = self.client.post(reverse("invitation-create"), {}, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(InvatationToken.objects.count(), 1)


class TutorPriceUpdateApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tutor = User.objects.create_user(
            email="tutor@example.test",
            password="Secure-test-password-123",
            name="Tutor",
            user_type="tutor",
        )
        self.student = User.objects.create_user(
            email="tutor-student@example.test",
            password="Secure-test-password-123",
            name="Tutor Student",
            user_type="regular",
            tutor=self.tutor,
        )
        self.client.force_authenticate(self.tutor)

    def test_tutor_can_update_own_price_per_class(self):
        response = self.client.patch(
            "/api/accounts/students/",
            {
                "student_id": str(self.student.account_id),
                "price_per_class": 25,
            },
            format="json",
        )

        self.student.refresh_from_db()
        self.tutor.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "student_id": str(self.student.account_id),
                "price_per_class": 25,
            },
        )
        self.assertEqual(self.student.price_per_class, 25)
        self.assertEqual(self.tutor.price_per_class, 15)

    def test_non_tutor_cannot_update_price_per_class(self):
        student = User.objects.create_user(
            email="student@example.test",
            password="Secure-test-password-123",
            name="Student",
            user_type="regular",
        )
        self.client.force_authenticate(student)

        response = self.client.patch(
            "/api/accounts/students/",
            {"price_per_class": 25},
            format="json",
        )

        student.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(student.price_per_class, 15)

    def test_price_per_class_must_be_nonnegative_integer(self):
        response = self.client.patch(
            "/api/accounts/students/",
            {
                "student_id": str(self.student.account_id),
                "price_per_class": -1,
            },
            format="json",
        )

        self.student.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.student.price_per_class, 15)

    def test_tutor_cannot_update_student_invited_by_another_tutor(self):
        other_tutor = User.objects.create_user(
            email="other-tutor@example.test",
            password="Secure-test-password-123",
            name="Other Tutor",
            user_type="tutor",
        )
        other_student = User.objects.create_user(
            email="other-student@example.test",
            password="Secure-test-password-123",
            name="Other Student",
            user_type="regular",
            tutor=other_tutor,
        )

        response = self.client.patch(
            "/api/accounts/students/",
            {
                "student_id": str(other_student.account_id),
                "price_per_class": 25,
            },
            format="json",
        )

        other_student.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(other_student.price_per_class, 15)
