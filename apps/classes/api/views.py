import base64
import hmac

from django.conf import settings
from rest_framework import viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from django.db.models import Q
from .serializers import (
    ClassesSerializer,
    ContentsSerializer,
    NotebookSerializer,
    YjsContentStateSerializer,
)
from apps.classes.models import Contents, Notebook
from apps.classes.service import (
    ClassesService,
    NotebookService,
    YjsContentService,
)


class CollaborationServicePermission(BasePermission):
    def has_permission(self, request, view):
        expected_token = settings.COLLABORATION_SERVICE_TOKEN
        provided_token = request.headers.get("X-Collaboration-Service-Key", "")
        return bool(
            expected_token
            and provided_token
            and hmac.compare_digest(expected_token, provided_token)
        )


class YjsContentStateView(APIView):
    authentication_classes = []
    permission_classes = [CollaborationServicePermission]

    def get(self, request, class_id):
        content = YjsContentService.get_yjs_content(class_id)
        return Response(
            {
                "state": base64.b64encode(
                    bytes(content.yjs_content)
                ).decode("ascii")
            }
        )

    def put(self, request, class_id):
        serializer = YjsContentStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content = YjsContentService.update_yjs_content(
            class_id,
            serializer.validated_data["state"],
        )
        return Response({"updated_at": content.updated_at})


class TutorBookedClassesView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        if request.user.user_type != "tutor":
            raise PermissionDenied("Only tutors can view booked classes.")

        booked_classes = ClassesService.get_booked_classes_for_tutor(request.user)
        serializer = ClassesSerializer(booked_classes, many=True)
        return Response(serializer.data)


class ClassesViewSet(viewsets.ModelViewSet):
    serializer_class = ClassesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ClassesService.get_classes_for_user(self.request.user)

    @action(detail=True, methods=["get", "put", "patch"], url_path="content")
    def content(self, request, pk=None):
        class_instance = self.get_object()
        contents, _ = Contents.objects.get_or_create(class_id=class_instance)

        if request.method == "GET":
            serializer = ContentsSerializer(contents)
            return Response(serializer.data)

        serializer = ContentsSerializer(
            contents,
            data=request.data,
            partial=request.method == "PATCH",
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="yjs-content")
    def yjs_content(self, request, pk=None):
        content = YjsContentService.create_yjs_content(
            {"class_id": pk},
            request.user,
        )
        return Response(
            {
                "document_name": f"class:{content.class_id_id}",
                "yjs_content_id": str(content.unique_id),
            }
        )

    def perform_create(self, serializer):
        class_data = serializer.validated_data
        serializer.instance = ClassesService.create_class(class_data, self.request.user)

    def perform_update(self, serializer):
        class_data = serializer.validated_data
        serializer.instance = ClassesService.update_class(
            serializer.instance,
            class_data,
            self.request.user,
        )

    def perform_destroy(self, instance):
        ClassesService.delete_class(instance, self.request.user)


class NotebookViewSet(viewsets.ModelViewSet):
    serializer_class = NotebookSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Notebook.objects.filter(
            Q(student=self.request.user) | Q(tutor=self.request.user)
        )

    def perform_create(self, serializer):
        serializer.instance = NotebookService.create_notebook(
            serializer.validated_data,
            self.request.user,
        )
