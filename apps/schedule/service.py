from .models import Schedule
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.accounts.models import User
from apps.classes.models import Classes
from .exceptions import UserTypeError


class ScheduleService:

    user_type_val=settings.TUTOR_USER


    @staticmethod
    def get_schedules_for_user(user):
        return Schedule.objects.filter(account_id=user.account_id)

    @staticmethod
    def get_tutor_schedules_for_user():
        return Schedule.objects.filter(activity_type__in=['available','unavailable'])

    @staticmethod
    def get_tutor_calendar():
        tutor = User.objects.filter(user_type="tutor").order_by(
            "created_at", "account_id"
        ).first()
        if tutor is None:
            raise ValidationError("No tutor is available.")

        availability = Schedule.objects.filter(
            account_id=tutor,
            activity_type__in=["available", "unavailable"],
        ).order_by("date_of")
        booked_classes = Classes.objects.filter(
            tutor=tutor,
            status__in=["scheduled", "rescheduled", "in_progress"],
        ).order_by("scheduled_date")
        return tutor, availability, booked_classes

    @staticmethod
    @transaction.atomic
    def create_schedule(class_data, user):
        """Create the class and its schedule for the given user."""
        from apps.classes.service import ClassesService

        date_validation = Schedule.date_validation(class_data["date_of"])
        if date_validation["status"] == 400:
            raise ValidationError(date_validation["message"])

        tutor = class_data.get("tutor")
        if tutor is None:
            raise ValidationError("A tutor is required to schedule a class.")

        ScheduleService.check_availability(
            tutor,
            class_data["date_of"],
            class_data["duration"],
        )

        class_object = ClassesService.create_class(
            {
                "scheduled_date": class_data["date_of"],
                "class_name": f'{user.name} - {class_data["date_of"]}',
                "duration": class_data["duration"],
                "status": class_data.get("status", "scheduled"),
                "tutor": tutor
            },
            user,
        )

        return Schedule.objects.create(
            account_id=user,
            class_id=class_object,
            schedule_name=f"Class with {user.name}",
            comments=class_data.get("comments"),
            activity_type="class",
            date_of=class_data["date_of"],
            duration=class_data["duration"],
        )


    @staticmethod
    def create_availability(user, data):
        if user.user_type != ScheduleService.user_type_val:
            raise UserTypeError("You can't select availability!") 

        return Schedule.objects.create(
                    account_id=user,
                    schedule_name=data["schedule_name"],
                    activity_type=data["activity_type"],
                    date_of=data["date_of"],
                    duration=data["duration"],
                )

    @staticmethod
    def check_availability(tutor, selected_date, duration):
        requested_end = selected_date + duration
        available_slots = Schedule.objects.filter(
            account_id=tutor,
            activity_type="available",
            date_of__lte=selected_date,
        )

        if not any(
            slot.date_of + slot.duration >= requested_end
            for slot in available_slots
        ):
            raise ValidationError(
                "The selected tutor is not available for the requested time and duration."
            )

        unavailable_slots = Schedule.objects.filter(
            account_id=tutor,
            activity_type="unavailable",
            date_of__lt=requested_end,
        )
        if any(
            slot.date_of + slot.duration > selected_date
            for slot in unavailable_slots
        ):
            raise ValidationError(
                "The selected tutor is unavailable during the requested time."
            )

        booked_classes = Classes.objects.filter(
            tutor=tutor,
            status__in=["scheduled", "rescheduled", "in_progress"],
            scheduled_date__lt=requested_end,
        )
        if any(
            class_object.scheduled_date + class_object.duration > selected_date
            for class_object in booked_classes
        ):
            raise ValidationError(
                "The selected tutor is unavailable during the requested time."
            )