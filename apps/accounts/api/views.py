import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.service import AccountService
from .serializers import RegisterSerializer, CustomTokenSerializer, build_user_payload
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated, AllowAny

logger = logging.getLogger(__name__)

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        print(request.data)
        if serializer.is_valid():
            user = AccountService.register_user(**serializer.validated_data)

            return Response({"user": user}, status=201)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetUserInfoView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        return Response(build_user_payload(user), status=200)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer