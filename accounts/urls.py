from django.urls import path
from .views import register_view, login_view, LogoutView

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
