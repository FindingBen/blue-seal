import uuid
from django.db import models

class Classes(models.Model):
    STATUS_CHOICE = [
        ("done", "Done"),
        ("in_progress", "In progress"),
        ("scheduled", "Scheduled"),
        ("rescheduled", "Rescheduled"),
        ("cancelled", "Cancelled"),
    ]
    class_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
    "accounts.User",
    on_delete=models.CASCADE,
    related_name="student_classes",
    null=True
    )
    tutor = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="tutored_classes",
        null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICE)
    scheduled_date = models.DateTimeField()
    duration = models.DurationField()
    class_name = models.CharField(max_length=255, default='Random Class')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Contents(models.Model):
    content_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class_id = models.OneToOneField(
        Classes,
        on_delete=models.CASCADE,
        related_name="contents",
        db_column="class_id",
    )
    class_content = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)