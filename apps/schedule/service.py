from .models import Schedule
from django.db import transaction
from rest_framework.exceptions import ValidationError


class ScheduleService:
    @staticmethod
    def get_schedules_for_user(user):
        return Schedule.objects.filter(account_id=user.account_id)

    @staticmethod
    @transaction.atomic
    def create_schedule(class_data, user):
        """Create the class and its schedule for the given user."""
        from apps.classes.service import ClassesService

        date_validation = Schedule.date_validation(class_data["date_of"])
        if date_validation["status"] == 400:
            raise ValidationError(date_validation["message"])

        class_object = ClassesService.create_class(
            {
                "scheduled_date": class_data["date_of"],
                "class_name": f'{user.name} - {class_data["date_of"]}',
                "duration": class_data["duration"],
                "status": class_data.get("status", "scheduled"),
            },
            user,
        )

        return Schedule.objects.create(
            account_id=user,
            class_id=class_object,
            schedule_name=f"Class with {user.name}",
            comments=class_data.get("comments"),
            date_of=class_data["date_of"],
            duration=class_data["duration"],
        )
