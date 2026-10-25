from rest_framework import serializers
from apps.schedule.models import Schedule


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = "__all__"
        read_only_fields = ["schedule_id", "account_id", "class_id"]