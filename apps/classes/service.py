from .models import Classes, Notebook
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.accounts.exceptions import (
    InsufficientClassBalanceError,
    WalletDoesNotExistError,
)
from apps.accounts.service import WalletTransactionService

class ClassesService:
    @staticmethod
    @transaction.atomic
    def create_class(class_data, user):
        """Create a class for the given user."""
        notebook = class_data.get("notebook")
        tutor = class_data["tutor"]
        if notebook is not None and (
            notebook.student_id != user.pk or notebook.tutor_id != tutor.pk
        ):
            raise ValidationError(
                "The notebook must belong to this student and tutor."
            )

        class_instance = Classes.objects.create(
            student=user,
            tutor=tutor,
            notebook=notebook,
            class_name=class_data["class_name"],
            scheduled_date=class_data["scheduled_date"],
            duration=class_data["duration"],
            status=class_data.get("status", "scheduled"),
        )
        try:
            WalletTransactionService.consume_class_credit(
                str(user.pk),
                str(class_instance.pk),
            )
        except (InsufficientClassBalanceError, WalletDoesNotExistError) as exc:
            raise ValidationError(str(exc)) from exc
        return class_instance

    @staticmethod
    def update_class(class_instance, class_data, user):
        """Update only the status of a class owned by the given user."""
        if set(class_data) != {"status"}:
            raise ValidationError("Only status can be updated.")
        if class_instance.student_id != user.pk:
            raise ValidationError("You do not own this class.")

        status = class_data["status"]
        valid_statuses = {value for value, _ in Classes.STATUS_CHOICE}
        if status not in valid_statuses:
            raise ValidationError("Invalid class status.")

        class_instance.status = status
        class_instance.save(update_fields=["status", "updated_at"])
        return class_instance

    @staticmethod
    def delete_class(class_instance, user):
        """Delete a class owned by the given user."""
        if class_instance.student_id != user.pk:
            raise ValidationError("You do not own this class.")

        return class_instance.delete()

    @staticmethod
    def get_classes_for_user(user):
        """Retrieve all classes for the given user."""
        return Classes.objects.filter(Q(student=user) | Q(tutor=user))

    @staticmethod
    def get_booked_classes_for_tutor(tutor):
        """Retrieve active booked classes assigned to a tutor."""
        return Classes.objects.filter(
            tutor=tutor,
            status__in=["scheduled", "rescheduled", "in_progress"],
        ).order_by("scheduled_date")


class NotebookService:
    @staticmethod
    @transaction.atomic
    def create_notebook(notebook_data, user):
        """Create a notebook for one of the tutor's students."""
        if user.user_type != "tutor":
            raise PermissionDenied("Only tutors can create notebooks.")

        student = notebook_data["student"]
        if student.user_type != "regular" or student.tutor_id != user.pk:
            raise ValidationError(
                "You can only create notebooks for your own students."
            )

        return Notebook.objects.create(student=student, tutor=user)