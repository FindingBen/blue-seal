from rest_framework import serializers
from apps.accounts.models import User
from apps.classes.models import Classes, Notebook
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
    notebook = serializers.PrimaryKeyRelatedField(
        queryset=Notebook.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Schedule
        fields = "__all__"
        read_only_fields = ["schedule_id", "account_id","class_id"]


class TutorScheduleUpdateSerializer(serializers.Serializer):
    class_id = serializers.UUIDField()
    date_of = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(
        choices=[("cancelled", "Cancelled"), ("rescheduled", "Rescheduled")],
        required=False,
    )

    def validate(self, attrs):
        if "class_id" not in attrs:
            raise serializers.ValidationError(
                {"class_id": "This field is required."}
            )

        if attrs.get("status") == "cancelled":
            if "date_of" in attrs:
                raise serializers.ValidationError(
                    {"date_of": "A cancelled class cannot also be rescheduled."}
                )
        elif "date_of" not in attrs:
            raise serializers.ValidationError(
                {"date_of": "Provide a new date to reschedule the class."}
            )

        return attrs

    def to_representation(self, instance):
        return {
            "class_id": str(instance.class_id_id),
            "date_of": self.fields["date_of"].to_representation(instance.date_of),
            "status": instance.class_id.status,
        }