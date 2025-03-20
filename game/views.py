from django.shortcuts import render

# Create your views here.
import random
import string
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from .models import Room, Player, Round, WolfList


def generate_unique_code(length=6):
    """Generate a unique room code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        if not Room.objects.filter(code=code).exists():
            return code


class CreateGameRoom(APIView):
    def post(self, request):
        """
        Create a new game room.
        The user becomes the host and a player in the room.
        """
        user = request.user  # Assuming the user is authenticated
        name = request.data.get("name")
        max_players = request.data.get("max_players", 10)

        if not name:
            return Response({"error": "Room name is required."}, status=status.HTTP_400_BAD_REQUEST)

        if max_players < 2:
            return Response({"error": "Max players must be at least 2."}, status=status.HTTP_400_BAD_REQUEST)

        code = generate_unique_code()
        room = Room.objects.create(
            name=name,
            code=code,
            host=user,
            max_players=max_players
        )

        # Add the host as the first player
        uid = code + "-" + user.id
        player = Player.objects.create(user=user, unique_id=uid)
        room.players.add(player)

        return Response({
            "message": "Room created successfully.",
            "room_code": room.code,
            "room_name": room.name,
            "max_players": room.max_players,
        }, status=status.HTTP_201_CREATED)


class JoinGameRoom(APIView):
    def post(self, request):
        """
        Join an existing game room using the room code.
        """
        user = request.user  # Assuming the user is authenticated
        room_code = request.data.get("room_code")

        if not room_code:
            return Response({"error": "Room code is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            room = Room.objects.get(code=room_code)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        if room.players.count() >= room.max_players:
            return Response({"error": "Room is full."}, status=status.HTTP_403_FORBIDDEN)
        
        uid = room_code + "-" + user.id

        # Check if the user is already in the room
        if Player.objects.filter(user=user, unique_id=uid).exists():
            return Response({"message": "You are already in this room."}, status=status.HTTP_200_OK)

        # Add the user as a player
        player = Player.objects.create(user=user, unique_id=uid)
        print("Before : ", room.players.count(), room.players.all())
        room.players.add(player)
        print("After : ", room.players.count(), room.players.all())

        return Response({
            "message": "Joined room successfully.",
            "room_code": room.code,
            "room_name": room.name,
            "current_players": room.players.count(),
            "max_players": room.max_players,
        }, status=status.HTTP_200_OK)

class LeaveGameRoom(APIView):
    def post(self, request):
        """
        Leave a game room.
        The player's model is deleted, and the room is updated accordingly.
        If the player is the host, either the host is transferred or the room is closed.
        """
        user = request.user  # Assuming the user is authenticated
        room_code = request.data.get("room_code")
        uid = room_code + "-" + user.id

        if not room_code:
            return Response({"error": "Room code is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            room = Room.objects.get(code=room_code)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            player = Player.objects.get(user=user, unique_id=uid)
        except Player.DoesNotExist:
            return Response({"error": "You are not part of this room."}, status=status.HTTP_403_FORBIDDEN)

        # Remove the player from the room
        player.delete()
        room.players.remove(player)

        # If the leaving player is the host
        if room.host == user:
            remaining_players = room.players.all()
            if remaining_players.exists():
                # Assign new host to the first remaining player
                new_host = remaining_players.first().user
                room.host = new_host
                room.save()
            else:
                # If no players are left, delete the room
                room.delete()
                return Response({
                    "message": "Room closed as no players are left.",
                }, status=status.HTTP_200_OK)

        return Response({
            "message": "You have left the room.",
            "room_code": room_code,
            "remaining_players": room.players.count()
        }, status=status.HTTP_200_OK)

class StartGame(APIView):
    def post(self, request):
        """
        Start the game for a specific room.
        Initializes the rounds and creates the WolfList for tracking wolfed users.
        """
        user = request.user  # Assuming the user is authenticated
        room_code = request.data.get("room_code")

        if not room_code:
            return Response({"error": "Room code is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            room = Room.objects.get(code=room_code)
        except Room.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the user is the host
        if room.host != user:
            return Response({"error": "Only the host can start the game."}, status=status.HTTP_403_FORBIDDEN)

        # Check if the game has already started
        if Round.objects.filter(room=room).exists():
            return Response({"error": "Game has already started for this room."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch all players in the room
        players = room.players.all()
        if players.count() < 2:
            return Response({"error": "At least 2 players are required to start the game."}, status=status.HTTP_400_BAD_REQUEST)

        # Initialize WolfList
        wolf_list, created = WolfList.objects.get_or_create(room=room)

        # Create Round models
        for i in range(1, players.count() + 1):
            Round.objects.create(
                room=room,
                wolf=None,  # To be assigned during gameplay
                question=f"Question for round {i}",  # Placeholder, can be customized
                wolf_ranking={},
                pack_ranking={},
                pack_score=0,
                round_number=i,
            )
        
        if room.game_started:
            return Response({"error": "Game has already started."}, status=status.HTTP_400_BAD_REQUEST)
        else :
            room.game_started = True
            room.save()

        return Response({
            "message": "Game has started!",
            "room_code": room.code,
            "num_players": players.count(),
            "num_rounds": players.count()
        }, status=status.HTTP_200_OK)
