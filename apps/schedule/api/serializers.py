from rest_framework import serializers
from apps.accounts.models import User
from apps.classes.models import Classes
from apps.schedule.models import Schedule


class CalendarAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ["schedule_id", "date_of", "duration", "activity_type"]


class BookedSessionSerializer(serializers.ModelSerializer):
    date_of = serializers.DateTimeField(source="scheduled_date")
    activity_type = serializers.SerializerMethodField()
    student_account_id = serializers.UUIDField(
        source="student_id", allow_null=True, read_only=True
    )

    class Meta:
        model = Classes
        fields = [
            "class_id",
            "date_of",
            "duration",
            "activity_type",
            "student_account_id",
        ]

    def get_activity_type(self, _class_object):
        return "booked"


class ScheduleSerializer(serializers.ModelSerializer):
    tutor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Schedule
        fields = "__all__"
        read_only_fields = ["schedule_id", "account_id","class_id"]