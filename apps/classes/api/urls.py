from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClassesViewSet, TutorBookedClassesView

router = DefaultRouter()
router.register(r'tutor/v1', TutorBookedClassesView, basename='tutor-booked-classes')
router.register(r'v1', ClassesViewSet, basename='classes')

urlpatterns = [
    path('', include(router.urls)),
]
