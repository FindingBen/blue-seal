import base64
import binascii

from rest_framework import serializers
from apps.accounts.models import User
from apps.classes.models import Classes, Contents, Notebook, YjsContent

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

class YjsContentSerializer(serializers.ModelSerializer):
    class_id = serializers.UUIDField(source="class_id_id", read_only=True)

    class Meta:
        model= YjsContent
        fields = ["yjs_content","created_at", "updated_at"]
        read_only_fields = ["unique_id","class_id","created_at", "updated_at"]


class YjsContentStateSerializer(serializers.Serializer):
    state = serializers.CharField(trim_whitespace=False)

    def validate_state(self, value):
        try:
            state = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise serializers.ValidationError(
                "State must be valid base64."
            ) from exc

        if not state:
            raise serializers.ValidationError("State cannot be empty.")
        return state