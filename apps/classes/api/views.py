from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from .serializers import ClassesSerializer, ContentsSerializer
from apps.classes.models import Contents
from apps.classes.service import ClassesService


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

    
