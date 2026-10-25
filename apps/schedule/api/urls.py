from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScheduleView

router = DefaultRouter()
router.register(r'v1', ScheduleView, basename='schedules')

urlpatterns = [
    path('', include(router.urls)),
]
