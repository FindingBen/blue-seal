from rest_framework import serializers
from apps.classes.models import Classes

class ClassesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classes
        fields = ['class_id', 'account_id', 'duration','class_name', 'scheduled_date','status', 'created_at', 'updated_at']
        read_only_fields = ['account_id', 'created_at', 'updated_at']