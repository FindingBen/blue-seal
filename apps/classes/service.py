from .models import Classes
from django.core.exceptions import ValidationError
from django.db.models import Q

class ClassesService:
    @staticmethod
    def create_class(class_data, user):
        """Create a class for the given user."""
        return Classes.objects.create(
            student=user,
            tutor=class_data["tutor"],
            class_name=class_data["class_name"],
            scheduled_date=class_data["scheduled_date"],
            duration=class_data["duration"],
            status=class_data.get("status", "scheduled"),
        )

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