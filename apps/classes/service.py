import math

from .models import Classes, Notebook, YjsContent
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
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
        if user.user_type != "regular":
            raise PermissionDenied("Only students can book classes.")

        notebook = class_data.get("notebook")
        tutor = class_data.get("tutor")
        if (
            tutor is None
            or tutor.user_type != "tutor"
            or user.tutor_id != tutor.pk
        ):
            raise ValidationError(
                "You can only book classes with your assigned tutor."
            )

        if notebook is None:
            notebook = ClassesService.get_matching_notebook(user, tutor)
        if notebook is None:
            raise ValidationError(
                "Your tutor must create a notebook before you can book a class."
            )
        if (
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
                max(1, math.ceil(class_data["duration"].total_seconds() / 3600)),
            )
        except (InsufficientClassBalanceError, WalletDoesNotExistError) as exc:
            raise ValidationError(str(exc)) from exc
        return class_instance

    @staticmethod
    def get_matching_notebook(student, tutor):
        return Notebook.objects.filter(
            student=student,
            tutor=tutor,
        ).order_by("created_at", "notebook_id").first()

    @staticmethod
    def update_class(class_instance, class_data, user):
        """Update allowed class fields for the class participant."""
        if user.user_type == "tutor":
            if class_instance.tutor_id != user.pk:
                raise ValidationError("You do not own this class.")
            if set(class_data) != {"class_name"}:
                raise ValidationError("Tutors can only update the class name.")

            class_instance.class_name = class_data["class_name"]
            class_instance.save(update_fields=["class_name", "updated_at"])
            return class_instance

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


class YjsContentService:
    @staticmethod
    @transaction.atomic
    def create_yjs_content(content_data, user):
        class_instance = Classes.objects.filter(
            class_id=content_data["class_id"],
        ).filter(
            Q(student=user, student__user_type="regular")
            | Q(tutor=user, tutor__user_type="tutor"),
        ).first()
        if class_instance is None:
            raise PermissionDenied(
                "You do not have access to this class notebook."
            )

        notebook = class_instance.notebook
        if notebook is None:
            notebook = ClassesService.get_matching_notebook(
                class_instance.student,
                class_instance.tutor,
            )
            if notebook is None:
                raise PermissionDenied(
                    "You do not have access to this class notebook."
                )
            class_instance.notebook = notebook
            class_instance.save(update_fields=["notebook"])
        elif (
            notebook.student_id != class_instance.student_id
            or notebook.tutor_id != class_instance.tutor_id
        ):
            raise PermissionDenied(
                "You do not have access to this class notebook."
            )

        content, _ = YjsContent.objects.get_or_create(
            class_id=class_instance,
            defaults={"yjs_content": b"\x00\x00"},
        )
        return content

    @staticmethod
    def get_yjs_content(class_id):
        try:
            return YjsContent.objects.get(class_id=class_id)
        except YjsContent.DoesNotExist as exc:
            raise NotFound("Yjs content not found.") from exc

    @staticmethod
    @transaction.atomic
    def update_yjs_content(class_id, state):
        try:
            content = YjsContent.objects.select_for_update().get(
                class_id=class_id
            )
        except YjsContent.DoesNotExist as exc:
            raise NotFound("Yjs content not found.") from exc

        content.yjs_content = state
        content.save(update_fields=["yjs_content", "updated_at"])
        return content