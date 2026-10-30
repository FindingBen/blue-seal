
from django.db import transaction
from .exceptions import InsufficientClassBalanceError, WalletDoesNotExistError
from .models import ClassLedger, User, Wallet


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

    @staticmethod
    def get_tutors():
        return User.objects.filter(user_type='tutor')


        # verification = EmailVerification.objects.create(user=user)



class WalletTransactionService:
    @staticmethod
    def get_wallet(user_id: str) -> Wallet:
        try:
            return Wallet.objects.get(user_id=user_id)
        except Wallet.DoesNotExist as exc:
            raise WalletDoesNotExistError(user_id) from exc

    @staticmethod
    @transaction.atomic
    def consume_class_credit(user_id: str, reference_id: str) -> None:
        try:
            wallet = Wallet.objects.select_for_update().get(user_id=user_id)
        except Wallet.DoesNotExist as exc:
            raise WalletDoesNotExistError(user_id) from exc

        if wallet.balance < 1:
            raise InsufficientClassBalanceError(wallet.balance)

        wallet.balance -= 1
        wallet.save(update_fields=["balance", "updated_at"])
        ClassLedger.objects.create(
            wallet=wallet,
            entry_type="debit",
            amount=1,
            reference_id=reference_id,
            note="Class booked",
        )

    @staticmethod
    @transaction.atomic
    def top_up_wallet(user_id:str, amount:int, payment_refferance: dict = None):
        try:
            wallet = Wallet.objects.select_for_update().get(user_id=user_id)
        except Wallet.DoesNotExist:
            return WalletDoesNotExistError(f"Wallet for user {user_id} does not exist.")

        wallet.balance += amount
        wallet.save(update_fields=["balance", "updated_at"])
        payment_refferance = payment_refferance or {}
        ClassLedger.objects.create(
            wallet=wallet,
            entry_type="top_up",
            amount=amount,
            reference_id=str(
                payment_refferance.get("payment_order_id")
                or payment_refferance.get("provider_charge_id")
                or ""
            ),
            note=payment_refferance.get("note", "Wallet top-up")
        )
        return True

    @staticmethod
    @transaction.atomic
    def reserve_funds(user_id:str, amount:int, reference_id:str = ""):
        try:
            wallet = Wallet.objects.select_for_update().get(user_id=user_id)
        except Wallet.DoesNotExist:
            return WalletDoesNotExistError(f"Wallet for user {user_id} does not exist.")

        if wallet.balance - wallet.reserved < amount:
            return InsufficientBalanceError(amount, wallet.balance - wallet.reserved)

        wallet.reserved += amount
        wallet.save(update_fields=["reserved", "updated_at"])
        ClassLedger.objects.create(
            wallet=wallet,
            entry_type="reservation",
            amount=amount,
            reference_id=reference_id,
            note="Funds reserved for SMS sending"
        )

        return True

    @staticmethod
    @transaction.atomic
    def release_reservation(user_id: str, amount: int, reference_id: str = ""):
        wallet = Wallet.objects.select_for_update().get(user_id=user_id)
        wallet.reserved -= amount
        wallet.save(update_fields=["reserved", "updated_at"])
        ClassLedger.objects.create(
            wallet=wallet,
            entry_type="adjustment",
            amount=amount,
            reference_id=reference_id,
            note="Released over-reservation after send settlement",
        )
        return True

    @staticmethod
    @transaction.atomic
    def debit_funds(user_id:str, amount:int, reference_id:str = "", note:str = ""):
        try:
            wallet = Wallet.objects.select_for_update().get(user_id=user_id)
        except Wallet.DoesNotExist:
            return WalletDoesNotExistError(f"Wallet for user {user_id} does not exist.")

        if wallet.reserved < amount:
            return InsufficientBalanceError(amount, wallet.reserved)

        wallet.reserved -= amount
        wallet.balance -= amount
        wallet.save(update_fields=["balance", "reserved", "updated_at"])
        ClassLedger.objects.create(
            wallet=wallet,
            entry_type="debit",
            amount=amount,
            reference_id=reference_id,
            note=note
        )

        return True

    @staticmethod
    @transaction.atomic
    def refund_funds(user_id:str, amount:int, reference_id:str = "", note:str = ""):
        try:
            wallet = Wallet.objects.select_for_update().get(user_id=user_id)
        except Wallet.DoesNotExist:
            return WalletDoesNotExistError(f"Wallet for user {user_id} does not exist.")

        wallet.balance += amount
        wallet.save(update_fields=["balance", "updated_at"])
        ClassLedger.objects.create(
            wallet=wallet,
            entry_type="refund",
            amount=amount,
            reference_id=reference_id,
            note=note
        )

        return True