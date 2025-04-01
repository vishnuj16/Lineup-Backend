from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
import json

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    data = json.loads(request.body)
    email = data.get("email")
    username = data.get("username")
    password = data.get("password")

    if not username or not password or not email:
        return JsonResponse({"error": "Username, email and password required"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "Username already taken"}, status=400)
    
    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already exists"}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password)

    if not user:
        return JsonResponse({"error": "User registration failed"}, status=400)
    
    return JsonResponse({"message": "Registration successful", "username": user.username}, status=201)

@api_view(['POST'])    
def login_view(request):
    data = json.loads(request.body)
    username = data.get("username")
    password = data.get("password")

    if username is None or password is None:
        return JsonResponse({'error': 'Please provide both username and password'}, status=400)

    user = authenticate(request, username=username, password=password)

    if user is None:
        user = authenticate(request, email=username, password=password)
        if user is None:
            return JsonResponse({'error': 'Invalid username or password'}, status=401)
    
    refresh = RefreshToken.for_user(user)
    if not refresh:
        return JsonResponse({'error': 'Token generation failed'}, status=400)
    return Response({
        'message': 'User created successfully',
        'user_id': user.id,   
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'username': user.username,
        'email': user.email,
        'user_id': user.id,    
    },
    status=status.HTTP_200_OK) 

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')

            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response({'message': 'User logged out successfully'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
