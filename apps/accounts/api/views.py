from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.service import AccountService
from .serializers import RegisterSerializer

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        print(request.data)
        if serializer.is_valid():
            user = AccountService.register_user(**serializer.validated_data)

            return Response({"user": user}, status=201)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)