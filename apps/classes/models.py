import uuid
from django.db import models

class Classes(models.Model):
    STATUS_CHOICE = [
        ("done", "Done"),
        ("in_progress", "In progress"),
        ("scheduled", "Scheduled"),
        ("cancelled", "Cancelled"),
    ]
    class_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_id = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="classes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICE)
    scheduled_date = models.DateTimeField()
    duration = models.DurationField()
    class_name = models.CharField(max_length=255, default='Random Class')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)