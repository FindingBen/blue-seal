import base64
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ClassLedger, Wallet
from apps.classes.models import Classes, Notebook, YjsContent
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


class YjsContentApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.tutor = user_model.objects.create_user(
            email="yjs-tutor@example.com",
            password="test-password",
            name="Tutor",
            user_type="tutor",
        )
        self.student = user_model.objects.create_user(
            email="yjs-student@example.com",
            password="test-password",
            name="Student",
            user_type="regular",
            tutor=self.tutor,
        )
        self.other_user = user_model.objects.create_user(
            email="yjs-other@example.com",
            password="test-password",
            name="Other",
            user_type="regular",
        )
        notebook = Notebook.objects.create(student=self.student, tutor=self.tutor)
        self.class_instance = Classes.objects.create(
            student=self.student,
            tutor=self.tutor,
            notebook=notebook,
            status="scheduled",
            scheduled_date=timezone.now() + timedelta(days=1),
            duration=timedelta(hours=1),
            class_name="Yjs test class",
        )
        self.client = APIClient()
        self.url = (
            f"/api/classes/v1/{self.class_instance.pk}/yjs-content/"
        )

    def test_class_participant_can_create_and_reuse_yjs_content(self):
        self.client.force_authenticate(self.student)

        first_response = self.client.post(self.url)
        second_response = self.client.post(self.url)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(YjsContent.objects.count(), 1)
        self.assertEqual(
            first_response.data["document_name"],
            f"class:{self.class_instance.pk}",
        )
        self.assertEqual(
            first_response.data["yjs_content_id"],
            second_response.data["yjs_content_id"],
        )

        self.client.force_authenticate(self.tutor)
        tutor_response = self.client.post(self.url)

        self.assertEqual(tutor_response.status_code, 200)
        self.assertEqual(
            tutor_response.data["yjs_content_id"],
            first_response.data["yjs_content_id"],
        )

    def test_non_participant_cannot_access_yjs_content(self):
        self.client.force_authenticate(self.other_user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(YjsContent.objects.exists())

    def test_existing_unlinked_class_uses_students_matching_notebook(self):
        self.class_instance.notebook = None
        self.class_instance.save(update_fields=["notebook"])
        self.client.force_authenticate(self.student)

        response = self.client.post(self.url)

        self.class_instance.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.class_instance.notebook, self.notebook)

    def test_class_without_matching_notebook_cannot_create_yjs_content(self):
        self.notebook.delete()
        self.class_instance.refresh_from_db()
        self.client.force_authenticate(self.student)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(YjsContent.objects.exists())

    def test_notebook_with_different_tutor_cannot_be_accessed(self):
        other_tutor = get_user_model().objects.create_user(
            email="yjs-other-tutor@example.com",
            password="test-password",
            name="Other tutor",
            user_type="tutor",
        )
        self.class_instance.notebook = Notebook.objects.create(
            student=self.student,
            tutor=other_tutor,
        )
        self.class_instance.save(update_fields=["notebook"])
        self.client.force_authenticate(self.student)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(YjsContent.objects.exists())

    def test_service_can_load_and_save_yjs_state(self):
        self.client.force_authenticate(self.student)
        self.client.post(self.url)
        state_url = (
            f"/api/classes/v1/{self.class_instance.pk}/yjs-content/state/"
        )
        encoded_state = base64.b64encode(b"\x01\x02").decode("ascii")

        with self.settings(COLLABORATION_SERVICE_TOKEN="node-service-secret"):
            get_response = self.client.get(
                state_url,
                HTTP_X_COLLABORATION_SERVICE_KEY="node-service-secret",
            )
            put_response = self.client.put(
                state_url,
                {"state": encoded_state},
                format="json",
                HTTP_X_COLLABORATION_SERVICE_KEY="node-service-secret",
            )
            saved_response = self.client.get(
                state_url,
                HTTP_X_COLLABORATION_SERVICE_KEY="node-service-secret",
            )

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.data["state"], base64.b64encode(b"\x00\x00").decode("ascii"))
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(
            saved_response.data["state"],
            encoded_state,
        )

    def test_state_api_rejects_missing_or_invalid_service_key(self):
        self.client.force_authenticate(self.student)
        state_url = (
            f"/api/classes/v1/{self.class_instance.pk}/yjs-content/state/"
        )

        with self.settings(COLLABORATION_SERVICE_TOKEN="node-service-secret"):
            missing_key_response = self.client.get(state_url)
            invalid_key_response = self.client.get(
                state_url,
                HTTP_X_COLLABORATION_SERVICE_KEY="wrong-secret",
            )

        self.assertEqual(missing_key_response.status_code, 403)
        self.assertEqual(invalid_key_response.status_code, 403)

    def test_state_api_rejects_invalid_base64(self):
        self.client.force_authenticate(self.student)
        self.client.post(self.url)
        state_url = (
            f"/api/classes/v1/{self.class_instance.pk}/yjs-content/state/"
        )

        with self.settings(COLLABORATION_SERVICE_TOKEN="node-service-secret"):
            response = self.client.put(
                state_url,
                {"state": "not-base64!"},
                format="json",
                HTTP_X_COLLABORATION_SERVICE_KEY="node-service-secret",
            )

        self.assertEqual(response.status_code, 400)


class NotebookApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.tutor = user_model.objects.create_user(
            email="notebook-tutor@example.com",
            ******,
            name="Tutor",
            user_type="tutor",
        )
        self.student = user_model.objects.create_user(
            email="notebook-student@example.com",
            ******,
            name="Student",
            user_type="regular",
            tutor=self.tutor,
        )
        self.client = APIClient()
        self.url = "/api/classes/notebooks/"

    def test_tutor_can_create_notebook_for_their_student(self):
        self.client.force_authenticate(self.tutor)

        response = self.client.post(
            self.url,
            {"student": str(self.student.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        notebook = Notebook.objects.get()
        self.assertEqual(notebook.student, self.student)
        self.assertEqual(notebook.tutor, self.tutor)

    def test_student_cannot_create_notebook(self):
        self.client.force_authenticate(self.student)

        response = self.client.post(
            self.url,
            {"student": str(self.student.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Notebook.objects.exists())


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


class TutorClassNameUpdateApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.tutor = user_model.objects.create_user(
            email="class-name-tutor@example.com",
            password="test-password",
            name="Tutor",
            user_type="tutor",
        )
        self.other_tutor = user_model.objects.create_user(
            email="class-name-other-tutor@example.com",
            password="test-password",
            name="Other tutor",
            user_type="tutor",
        )
        self.student = user_model.objects.create_user(
            email="class-name-student@example.com",
            password="test-password",
            name="Student",
            user_type="regular",
        )
        self.class_instance = Classes.objects.create(
            student=self.student,
            tutor=self.tutor,
            status="scheduled",
            scheduled_date=timezone.now() + timedelta(days=1),
            duration=timedelta(hours=1),
            class_name="Original class name",
        )
        self.client = APIClient()
        self.url = f"/api/classes/v1/{self.class_instance.pk}/"

    def test_assigned_tutor_can_update_class_name(self):
        self.client.force_authenticate(self.tutor)

        response = self.client.patch(
            self.url,
            {"class_name": "Updated class name"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.class_instance.refresh_from_db()
        self.assertEqual(self.class_instance.class_name, "Updated class name")

    def test_other_tutor_cannot_update_class_name(self):
        self.client.force_authenticate(self.other_tutor)

        response = self.client.patch(
            self.url,
            {"class_name": "Unauthorized name"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.class_instance.refresh_from_db()
        self.assertEqual(self.class_instance.class_name, "Original class name")


class ClassBookingWalletTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.tutor = user_model.objects.create_user(
            email="wallet-booking-tutor@example.com",
            password="test-password",
            name="Tutor",
            user_type="tutor",
        )
        self.student = user_model.objects.create_user(
            email="wallet-booking-student@example.com",
            password="test-password",
            name="Student",
            user_type="regular",
            tutor=self.tutor,
        )
        self.wallet = Wallet.objects.create(user=self.student, balance=1)
        self.notebook = Notebook.objects.create(
            student=self.student,
            tutor=self.tutor,
        )
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
        self.assertEqual(
            Classes.objects.get(student=self.student).notebook,
            self.notebook,
        )

    def test_booking_without_tutor_created_notebook_is_rejected(self):
        self.notebook.delete()

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
        self.assertFalse(Classes.objects.filter(student=self.student).exists())
        self.assertEqual(self.wallet.balance, 1)

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
        self.assertEqual(
            Classes.objects.get(student=self.student).notebook,
            self.notebook,
        )

    def test_student_cannot_book_with_another_students_notebook(self):
        user_model = get_user_model()
        other_tutor = user_model.objects.create_user(
            email="other-booking-tutor@example.com",
            password="test-password",
            name="Other tutor",
            user_type="tutor",
        )
        other_student = user_model.objects.create_user(
            email="other-booking-student@example.com",
            password="test-password",
            name="Other student",
            user_type="regular",
            tutor=other_tutor,
        )
        other_notebook = Notebook.objects.create(
            student=other_student,
            tutor=other_tutor,
        )

        response = self.client.post(
            "/api/classes/v1/",
            {
                "tutor": str(self.tutor.pk),
                "notebook": str(other_notebook.pk),
                "class_name": "Invalid notebook booking",
                "scheduled_date": self.class_date.isoformat(),
                "duration": "01:00:00",
                "status": "scheduled",
            },
            format="json",
        )

        self.wallet.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Classes.objects.filter(student=self.student).exists())
        self.assertEqual(self.wallet.balance, 1)

    def test_booking_two_hours_deducts_two_class_credits(self):
        self.wallet.balance = 2
        self.wallet.save(update_fields=["balance"])

        response = self.client.post(
            "/api/schedule/v1/",
            {
                "tutor": str(self.tutor.pk),
                "date_of": self.class_date.isoformat(),
                "duration": "02:00:00",
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
                amount=2,
            ).count(),
            1,
        )

    def test_booking_more_hours_than_credits_is_rejected(self):
        self.wallet.balance = 2
        self.wallet.save(update_fields=["balance"])

        response = self.client.post(
            "/api/classes/v1/",
            {
                "tutor": str(self.tutor.pk),
                "class_name": "Three-hour booking",
                "scheduled_date": self.class_date.isoformat(),
                "duration": "03:00:00",
                "status": "scheduled",
            },
            format="json",
        )

        self.wallet.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.wallet.balance, 2)
        self.assertEqual(Classes.objects.filter(student=self.student).count(), 0)
        self.assertEqual(ClassLedger.objects.filter(wallet=self.wallet).count(), 0)
