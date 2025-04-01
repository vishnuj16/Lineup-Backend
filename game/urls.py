from django.urls import path
from .views import CreateGameRoom, JoinGameRoom, LeaveGameRoom, StartGame, GetRoomDetails

urlpatterns = [
    path("create-room/", CreateGameRoom.as_view(), name="create_room"),
    path("join-room/", JoinGameRoom.as_view(), name="join_room"),
    path("leave-room/", LeaveGameRoom.as_view(), name="leave_room"),
    path("start-game/", StartGame.as_view(), name="start_game"),
    path("get-room-details/", GetRoomDetails.as_view(), name="get_players"),
]
