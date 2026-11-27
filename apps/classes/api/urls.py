from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClassesViewSet,
    NotebookViewSet,
    TutorBookedClassesView,
    YjsContentStateView,
)

router = DefaultRouter()
router.register(r'tutor/v1', TutorBookedClassesView, basename='tutor-booked-classes')
router.register(r'notebooks', NotebookViewSet, basename='notebooks')
router.register(r'v1', ClassesViewSet, basename='classes')

urlpatterns = [
    path(
        "v1/<uuid:class_id>/yjs-content/state/",
        YjsContentStateView.as_view(),
        name="yjs-content-state",
    ),
    path('', include(router.urls)),
]
