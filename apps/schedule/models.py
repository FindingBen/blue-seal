import uuid
from django.db import models
from django.utils import timezone



class Schedule(models.Model):
    """Schedule model"""
    ACTIVITY_CHOICE = (('class','Class'),('unavailable','Unavailable'),('available','Available'))
    
    schedule_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_id = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="schedules")
    class_id = models.ForeignKey("classes.Classes", on_delete=models.CASCADE, related_name="schedules", null=True, blank=True)
    schedule_name = models.CharField(max_length=255, default='Random schedule')
    comments = models.TextField(max_length=500, default=None, null=True)
    date_of = models.DateTimeField()
    duration = models.DurationField()
    activity_type = models.CharField(max_length=255, choices=ACTIVITY_CHOICE , null=True)

    def handle_name(self, account_id):
        """Func for name handle"""
        from apps.accounts.models import User

        account_name = User.objects.get(account_id)
        str_schedule_name = f'Class with {account_name.name}'

        return str_schedule_name

    @staticmethod
    def date_validation(date_of):
        if date_of < timezone.now():
            return {"message":'Date cant be in the past', "status":400}
        return {"message":'Valid', "status":200}
    
