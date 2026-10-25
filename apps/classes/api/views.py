from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.core.exceptions import ValidationError
from .serializers import ClassesSerializer
from apps.classes.service import ClassesService


class ClassesViewSet(viewsets.ModelViewSet):
    serializer_class = ClassesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ClassesService.get_classes_for_user(self.request.user)

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

    

