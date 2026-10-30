import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.service import AccountService
from .serializers import (
    RegisterSerializer,
    TutorSerializer,
    CustomTokenSerializer,
    build_user_payload,
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated, AllowAny
from apps.accounts.exceptions import WalletDoesNotExistError
from apps.accounts.service import WalletTransactionService

logger = logging.getLogger(__name__)

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        print(request.data)
        if serializer.is_valid():
            user = AccountService.register_user(**serializer.validated_data)

            return Response({"user": user}, status=201)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TutorView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tutors = AccountService.get_tutors()
        return Response(
            {"tutors": TutorSerializer(tutors, many=True).data},
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