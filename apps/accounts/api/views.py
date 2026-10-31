import logging
import stripe
from django.conf import settings
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.service import AccountService
from .serializers import (
    RegisterSerializer,
    TutorSerializer,
    TutorPriceUpdateSerializer,
    CustomTokenSerializer,
    build_user_payload
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated, AllowAny
from apps.accounts.exceptions import WalletDoesNotExistError
from apps.accounts.models import InvatationToken
from apps.accounts.service import WalletTransactionService

logger = logging.getLogger(__name__)

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    user = AccountService.register_user(
                        **serializer.validated_data
                    )
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    customer = stripe.Customer.create(
                        name=user.name,
                        email=user.email,
                        metadata={"account_id": str(user.pk)},
                    )
                    user.stripe_customer_id = customer.id
                    user.save(update_fields=["stripe_customer_id"])
            except stripe.StripeError:
                logger.exception(
                    "Could not create Stripe customer during registration."
                )
                return Response(
                    {"error": "Unable to complete account registration."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            return Response(
                {"user": build_user_payload(user)},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InvitationTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.user_type != "tutor":
            return Response(
                {"error": "Only tutors can create invitation tokens."},
                status=status.HTTP_403_FORBIDDEN,
            )

        invitation = InvatationToken.objects.create(created_by=request.user)
        return Response(
            {
                "token": str(invitation.token),
                "created_at": invitation.created_at,
                "expires_at": invitation.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class TutorView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tutors = AccountService.get_tutors()
        return Response(
            {"tutors": TutorSerializer(tutors, many=True).data},
            status=status.HTTP_200_OK,
        )

class StudentView(APIView):
    permission_classes=[IsAuthenticated]

    def get(self, request):
        students = AccountService.get_students()
        return Response(
                    {"students": TutorSerializer(students, many=True).data},
                    status=status.HTTP_200_OK,
                )

    def patch(self, request):
        if request.user.user_type != "tutor":
            return Response(
                {"error": "Only tutors can update the class price."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TutorPriceUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        student = AccountService.get_students().filter(
            account_id=serializer.validated_data["student_id"],
            tutor=request.user,
        ).first()
        if student is None:
            return Response(
                {"error": "Student not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        student.price_per_class = serializer.validated_data["price_per_class"]
        student.save(update_fields=["price_per_class"])
        return Response(
            {
                "student_id": str(student.account_id),
                "price_per_class": student.price_per_class,
            },
            status=status.HTTP_200_OK,
        )

class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet = WalletTransactionService.get_wallet(request.user.pk)
        except WalletDoesNotExistError:
            return Response(
                {"error": "Wallet not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "balance": wallet.balance,
                "reserved": wallet.reserved,
                "available": wallet.balance - wallet.reserved,
                "updated_at": wallet.updated_at,
            },
            status=status.HTTP_200_OK,
        )

class GetUserInfoView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        return Response(build_user_payload(user), status=200)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer