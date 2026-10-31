from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.schedule.admin import ScheduleAdmin
from apps.schedule.api.views import TutorCalendarView
from apps.schedule.models import Schedule
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


class CreateAvailabilityTests(SimpleTestCase):
    def setUp(self):
        self.tutor = SimpleNamespace(user_type=ScheduleService.user_type_val)
        self.available_start = datetime(2026, 10, 31, 8, tzinfo=timezone.utc)
        self.available_slot = SimpleNamespace(
            account_id=self.tutor,
            class_id=None,
            schedule_name="Available",
            comments=None,
            activity_type="available",
            date_of=self.available_start,
            duration=timedelta(hours=12),
            save=Mock(),
            delete=Mock(),
        )

    def create_unavailability(self, start, duration):
        return ScheduleService.create_availability.__wrapped__(
            self.tutor,
            {
                "schedule_name": "Unavailable",
                "activity_type": "unavailable",
                "date_of": start,
                "duration": duration,
            },
        )

    @patch("apps.schedule.service.Schedule.objects.create")
    @patch("apps.schedule.service.Schedule.objects.filter")
    def test_unavailable_at_start_shortens_available_slot(
        self, filter_schedules, create_schedule
    ):
        filter_schedules.return_value = [self.available_slot]
        unavailable_start = self.available_start
        create_schedule.side_effect = lambda **fields: SimpleNamespace(**fields)

        self.create_unavailability(unavailable_start, timedelta(hours=3))

        self.assertEqual(
            self.available_slot.date_of,
            datetime(2026, 10, 31, 11, tzinfo=timezone.utc),
        )
        self.assertEqual(self.available_slot.duration, timedelta(hours=9))
        self.available_slot.save.assert_called_once_with(
            update_fields=["date_of", "duration"]
        )
        self.available_slot.delete.assert_not_called()
        create_schedule.assert_called_once()

    @patch("apps.schedule.service.Schedule.objects.create")
    @patch("apps.schedule.service.Schedule.objects.filter")
    def test_unavailable_in_middle_splits_available_slot(
        self, filter_schedules, create_schedule
    ):
        filter_schedules.return_value = [self.available_slot]
        create_schedule.side_effect = lambda **fields: SimpleNamespace(**fields)
        unavailable_start = datetime(2026, 10, 31, 11, tzinfo=timezone.utc)

        self.create_unavailability(unavailable_start, timedelta(hours=1))

        self.assertEqual(self.available_slot.date_of, self.available_start)
        self.assertEqual(self.available_slot.duration, timedelta(hours=3))
        self.available_slot.save.assert_called_once_with(
            update_fields=["date_of", "duration"]
        )
        self.assertEqual(create_schedule.call_count, 2)
        create_schedule.assert_any_call(
            account_id=self.tutor,
            class_id=None,
            schedule_name="Available",
            comments=None,
            activity_type="available",
            date_of=datetime(2026, 10, 31, 12, tzinfo=timezone.utc),
            duration=timedelta(hours=8),
        )

    @patch("apps.schedule.service.Schedule.objects.create")
    @patch("apps.schedule.service.Schedule.objects.filter")
    def test_unavailable_covering_slot_removes_availability(
        self, filter_schedules, create_schedule
    ):
        filter_schedules.return_value = [self.available_slot]
        create_schedule.side_effect = lambda **fields: SimpleNamespace(**fields)

        self.create_unavailability(
            self.available_start - timedelta(hours=1),
            timedelta(hours=14),
        )

        self.available_slot.delete.assert_called_once()
        self.available_slot.save.assert_not_called()
        create_schedule.assert_called_once()


class ScheduleAdminTests(SimpleTestCase):
    @patch("apps.schedule.admin.ScheduleService.apply_unavailability")
    def test_new_unavailable_schedule_cuts_existing_availability(
        self, apply_unavailability
    ):
        schedule = SimpleNamespace(
            _state=SimpleNamespace(adding=True),
            activity_type="unavailable",
            save=Mock(),
        )
        schedule_admin = ScheduleAdmin(Schedule, AdminSite())

        schedule_admin.save_model(object(), schedule, None, False)

        schedule.save.assert_called_once()
        apply_unavailability.assert_called_once_with(schedule)


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
