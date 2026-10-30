from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ClassLedger, Wallet
from apps.classes.models import Classes
from apps.schedule.models import Schedule


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


class ClassBookingWalletTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.student = user_model.objects.create_user(
            email="wallet-booking-student@example.com",
            password="test-password",
            name="Student",
            user_type="regular",
        )
        self.tutor = user_model.objects.create_user(
            email="wallet-booking-tutor@example.com",
            password="test-password",
            name="Tutor",
            user_type="tutor",
        )
        self.wallet = Wallet.objects.create(user=self.student, balance=1)
        self.client = APIClient()
        self.client.force_authenticate(self.student)
        self.class_date = timezone.now() + timedelta(days=2)
        Schedule.objects.create(
            account_id=self.tutor,
            activity_type="available",
            date_of=self.class_date - timedelta(hours=1),
            duration=timedelta(hours=3),
        )

    def test_booking_deducts_one_class_credit(self):
        response = self.client.post(
            "/api/schedule/v1/",
            {
                "tutor": str(self.tutor.pk),
                "date_of": self.class_date.isoformat(),
                "duration": "01:00:00",
                "activity_type": "class",
            },
            format="json",
        )

        self.wallet.refresh_from_db()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.wallet.balance, 0)
        self.assertEqual(
            ClassLedger.objects.filter(
                wallet=self.wallet,
                entry_type="debit",
                amount=1,
            ).count(),
            1,
        )
        self.assertEqual(Classes.objects.filter(student=self.student).count(), 1)

    def test_booking_without_class_credit_is_rejected_without_creating_booking(self):
        self.wallet.balance = 0
        self.wallet.save(update_fields=["balance"])

        response = self.client.post(
            "/api/schedule/v1/",
            {
                "tutor": str(self.tutor.pk),
                "date_of": self.class_date.isoformat(),
                "duration": "01:00:00",
                "activity_type": "class",
            },
            format="json",
        )

        self.wallet.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Classes.objects.filter(student=self.student).count(), 0)
        self.assertEqual(Schedule.objects.filter(account_id=self.student).count(), 0)
        self.assertEqual(self.wallet.balance, 0)
        self.assertEqual(ClassLedger.objects.filter(wallet=self.wallet).count(), 0)

    def test_direct_class_booking_also_requires_and_spends_credit(self):
        response = self.client.post(
            "/api/classes/v1/",
            {
                "tutor": str(self.tutor.pk),
                "class_name": "Direct booking",
                "scheduled_date": self.class_date.isoformat(),
                "duration": "01:00:00",
                "status": "scheduled",
            },
            format="json",
        )

        self.wallet.refresh_from_db()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.wallet.balance, 0)
        self.assertEqual(Classes.objects.filter(student=self.student).count(), 1)
