from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.exceptions import WalletDoesNotExistError
from apps.accounts.models import User, Wallet
from apps.accounts.service import WalletTransactionService
from rest_framework.test import APIClient


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
