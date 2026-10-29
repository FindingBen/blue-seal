from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScheduleView, TutorCalendarView, TutorScheduleView

router = DefaultRouter()
router.register(r'v1', ScheduleView, basename='schedules')
router.register(r'tutor/v1', TutorScheduleView, basename='tutor_schedules')

urlpatterns = [
    path('tutor/calendar/', TutorCalendarView.as_view(), name='tutor-calendar'),
    path('', include(router.urls)),
]
