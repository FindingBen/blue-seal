from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.schedule.api.views import TutorCalendarView
from apps.schedule.service import ScheduleService


class CheckAvailabilityTests(SimpleTestCase):
    def setUp(self):
        self.selected_date = datetime(2026, 11, 5, 14, tzinfo=timezone.utc)
        self.duration = timedelta(hours=1)
        self.available_slot = SimpleNamespace(
            date_of=datetime(2026, 11, 5, 13, tzinfo=timezone.utc),
            duration=timedelta(hours=3),
        )

    @patch("apps.schedule.service.Classes.objects.filter", return_value=[])
    @patch("apps.schedule.service.Schedule.objects.filter")
    def test_accepts_class_inside_available_slot_without_unavailable_overlap(
        self, filter_schedules, filter_classes
    ):
        filter_schedules.side_effect = lambda **filters: (
            [self.available_slot]
            if filters["activity_type"] == "available"
            else []
        )

        ScheduleService.check_availability(
            object(), self.selected_date, self.duration
        )

    @patch("apps.schedule.service.Classes.objects.filter", return_value=[])
    @patch("apps.schedule.service.Schedule.objects.filter")
    def test_rejects_class_overlapping_unavailable_slot(
        self, filter_schedules, filter_classes
    ):
        unavailable_slot = SimpleNamespace(
            date_of=self.selected_date + timedelta(minutes=30),
            duration=timedelta(hours=1),
        )
        filter_schedules.side_effect = lambda **filters: (
            [self.available_slot]
            if filters["activity_type"] == "available"
            else [unavailable_slot]
        )

        with self.assertRaisesMessage(
            ValidationError,
            "The selected tutor is unavailable during the requested time.",
        ):
            ScheduleService.check_availability(
                object(), self.selected_date, self.duration
            )

    @patch("apps.schedule.service.Classes.objects.filter", return_value=[])
    @patch("apps.schedule.service.Schedule.objects.filter")
    def test_rejects_class_outside_available_slots(
        self, filter_schedules, filter_classes
    ):
        filter_schedules.side_effect = lambda **filters: []

        with self.assertRaisesMessage(
            ValidationError,
            "The selected tutor is not available for the requested time and duration.",
        ):
            ScheduleService.check_availability(
                object(), self.selected_date, self.duration
            )

    @patch("apps.schedule.service.Classes.objects.filter")
    @patch("apps.schedule.service.Schedule.objects.filter")
    def test_rejects_class_overlapping_an_existing_booking(
        self, filter_schedules, filter_classes
    ):
        existing_class = SimpleNamespace(
            scheduled_date=self.selected_date + timedelta(minutes=30),
            duration=timedelta(hours=1),
        )
        filter_schedules.side_effect = lambda **filters: (
            [self.available_slot]
            if filters["activity_type"] == "available"
            else []
        )
        filter_classes.return_value = [existing_class]

        with self.assertRaisesMessage(
            ValidationError,
            "The selected tutor is unavailable during the requested time.",
        ):
            ScheduleService.check_availability(
                object(), self.selected_date, self.duration
            )


class TutorCalendarViewTests(SimpleTestCase):
    @patch("apps.schedule.api.views.ScheduleService.get_tutor_calendar")
    def test_returns_tutor_availability_and_booked_sessions(self, get_calendar):
        tutor_id = uuid4()
        schedule_id = uuid4()
        class_id = uuid4()
        student_id = uuid4()
        session_date = datetime(2026, 11, 5, 14, tzinfo=timezone.utc)
        get_calendar.return_value = (
            SimpleNamespace(account_id=tutor_id),
            [
                SimpleNamespace(
                    schedule_id=schedule_id,
                    date_of=session_date,
                    duration=timedelta(hours=3),
                    activity_type="available",
                )
            ],
            [
                SimpleNamespace(
                    class_id=class_id,
                    student_id=student_id,
                    scheduled_date=session_date,
                    duration=timedelta(hours=1),
                )
            ],
        )
        request = APIRequestFactory().get("/api/schedule/tutor/calendar/")
        force_authenticate(
            request, user=SimpleNamespace(is_authenticated=True)
        )

        response = TutorCalendarView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "tutor": str(tutor_id),
                "availability": [
                    {
                        "schedule_id": str(schedule_id),
                        "date_of": "2026-11-05T14:00:00Z",
                        "duration": "03:00:00",
                        "activity_type": "available",
                    }
                ],
                "booked": [
                    {
                        "class_id": str(class_id),
                        "date_of": "2026-11-05T14:00:00Z",
                        "duration": "01:00:00",
                        "activity_type": "booked",
                        "student_account_id": str(student_id),
                    }
                ],
            },
        )
