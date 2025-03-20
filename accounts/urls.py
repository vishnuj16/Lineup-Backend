from django.urls import path
from .views import register_view, login_view, logout_view, user_info, get_csrf_token

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("user/", user_info, name="user_info"),
    path('csrf/', get_csrf_token, name='csrf'),
]
