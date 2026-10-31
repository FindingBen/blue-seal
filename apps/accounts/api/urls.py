from django.urls import path
from .views import (
    GetUserInfoView,
    InvitationTokenView,
    LoginView,
    RegisterView,
    TutorView,
    WalletView,
    StudentView
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("invitations/", InvitationTokenView.as_view(), name="invitation-create"),
    path("login/", LoginView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("me/", GetUserInfoView.as_view()),
    path('tutors/', TutorView.as_view()),
    path('wallet/', WalletView.as_view(), name="wallet"),
    path('students/', StudentView.as_view()),
]