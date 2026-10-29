from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.classes.models import Classes


class ClassContentsApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.student = user_model.objects.create_user(
            email="student@example.com",
            password="test-password",
            name="Student",
            user_type="regular",
        )
        self.tutor = user_model.objects.create_user(
            email="tutor@example.com",
            password="test-password",
            name="Tutor",
            user_type="tutor",
        )
        self.class_instance = Classes.objects.create(
            student=self.student,
            tutor=self.tutor,
            status="done",
            scheduled_date=timezone.now(),
            duration=timedelta(hours=1),
            class_name="Test class",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.student)
        self.url = f"/api/classes/v1/{self.class_instance.pk}/content/"

    def test_class_content_can_be_read_and_autosaved(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["class_content"])
        self.assertEqual(response.data["class_id"], str(self.class_instance.pk))

        content = {"notes": ["Reviewed vocabulary", "Practiced conversation"]}
        response = self.client.patch(self.url, {"class_content": content}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["class_content"], content)


class TutorBookedClassesApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.tutor = user_model.objects.create_user(
            email="bookings-tutor@example.com",
            password="test-password",
            name="Tutor",
            user_type="tutor",
        )
        self.other_tutor = user_model.objects.create_user(
            email="other-tutor@example.com",
            password="test-password",
            name="Other tutor",
            user_type="tutor",
        )
        self.student = user_model.objects.create_user(
            email="bookings-student@example.com",
            password="test-password",
            name="Student",
            user_type="regular",
        )
        self.booked_class = Classes.objects.create(
            student=self.student,
            tutor=self.tutor,
            status="scheduled",
            scheduled_date=timezone.now() + timedelta(days=1),
            duration=timedelta(hours=1),
            class_name="Booked class",
        )
        Classes.objects.create(
            student=self.student,
            tutor=self.tutor,
            status="done",
            scheduled_date=timezone.now() - timedelta(days=2),
            duration=timedelta(hours=1),
            class_name="Completed class",
        )
        Classes.objects.create(
            student=self.student,
            tutor=self.other_tutor,
            status="scheduled",
            scheduled_date=timezone.now() + timedelta(days=2),
            duration=timedelta(hours=1),
            class_name="Other tutor class",
        )
        self.client = APIClient()
        self.url = "/api/classes/tutor/v1/"

    def test_tutor_receives_only_active_classes_assigned_to_them(self):
        self.client.force_authenticate(self.tutor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [class_data["class_id"] for class_data in response.data],
            [str(self.booked_class.pk)],
        )

    def test_non_tutor_cannot_view_tutor_bookings(self):
        self.client.force_authenticate(self.student)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
