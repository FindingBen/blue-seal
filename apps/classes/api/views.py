from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
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
        try:
            campaign_data = serializer.validated_data
            campaign = ClassesService.create_class(campaign_data, self.request.user)
            serializer.instance = campaign
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        try:
            campaign_data = serializer.validated_data
            campaign = ClassesService.update_class(serializer.instance, campaign_data, self.request.user)
            serializer.instance = campaign
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

    def perform_destroy(self, instance):
        try:
            ClassesService.delete_class(instance, self.request.user)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

    
