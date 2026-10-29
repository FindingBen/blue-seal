from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import (
    BookedSessionSerializer,
    CalendarAvailabilitySerializer,
    ScheduleSerializer,
)
from apps.schedule.service import ScheduleService


class TutorCalendarView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tutor, availability, booked_classes = ScheduleService.get_tutor_calendar()
        return Response(
            {
                "tutor": str(tutor.account_id),
                "availability": CalendarAvailabilitySerializer(
                    availability, many=True
                ).data,
                "booked": BookedSessionSerializer(booked_classes, many=True).data,
            }
        )


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

class TutorScheduleView(viewsets.ModelViewSet):
    serializer_class = ScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        "Get shcedules for user"
        return ScheduleService.get_tutor_schedules_for_user()

    def perform_create(self, serializer):
        class_data = serializer.validated_data
        schedule = ScheduleService.create_availability(self.request.user, class_data)
        serializer.instance = schedule