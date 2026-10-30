class DomainError(Exception):
    """Base class for domain-specific errors."""
    pass

class WalletDoesNotExistError(DomainError):
    """Raised when a user's wallet is not found."""
    def __init__(self, user_id):
        super().__init__(f"Wallet does not exist for user ID {user_id}")
        self.user_id = user_id


class InsufficientClassBalanceError(DomainError):
    """Raised when a user tries to book more classes than their wallet holds."""

    def __init__(self, balance):
        super().__init__(
            f"Not enough class credits. You have {balance} class credit(s); "
            "booking requires 1."
        )
        self.balance = balance