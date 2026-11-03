from rest_framework import serializers
from apps.accounts.models import User
from apps.classes.models import Classes, Contents, Notebook

class ClassesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classes
        fields = [
            "class_id",
            "student",
            "tutor",
            "notebook",
            "duration",
            "class_name",
            "scheduled_date",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ['student', 'created_at', 'updated_at']


class NotebookSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Notebook
        fields = ["notebook_id", "student", "tutor", "created_at", "updated_at"]
        read_only_fields = ["notebook_id", "tutor", "created_at", "updated_at"]


class ContentsSerializer(serializers.ModelSerializer):
    class_id = serializers.UUIDField(source="class_id_id", read_only=True)
    class_content = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = Contents
        fields = ["content_id", "class_id", "class_content", "created_at", "updated_at"]
        read_only_fields = ["content_id", "class_id", "created_at", "updated_at"]