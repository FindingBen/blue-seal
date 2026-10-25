from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .serializers import ScheduleSerializer
from apps.schedule.service import ScheduleService


class ScheduleView(viewsets.ModelViewSet):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        "Get shcedules for user"
        return ScheduleService.get_schedules_for_user(self.request.user)

    def perform_create(self, serializer):
        class_data = serializer.validated_data
        schedule = ScheduleService.create_schedule(class_data, self.request.user)
        serializer.instance = schedule
