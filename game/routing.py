# routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/lobby/(?P<room_code>\w+)/$', consumers.GameLobbyConsumer.as_asgi()),
    re_path(r'ws/game/(?P<room_code>\w+)/$', consumers.GameplayConsumer.as_asgi()),
]