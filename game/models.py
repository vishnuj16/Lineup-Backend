from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    # game_room = models.ForeignKey(Room, related_name="players", on_delete=models.CASCADE)
    unique_id = models.CharField(max_length=100, default="")
    score = models.IntegerField(default=0)

class Room(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=6)
    host = models.ForeignKey(User, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player, related_name="players")
    created_at = models.DateTimeField(auto_now_add=True)
    max_players = models.IntegerField(default=10)
    game_started = models.BooleanField(default=False)

class Round(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    wolf = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    question = models.CharField(max_length=255)
    wolf_ranking = models.JSONField(default=dict)
    pack_ranking = models.JSONField(default=dict)
    pack_score = models.IntegerField(default=0)
    round_number = models.IntegerField()

class Game(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    current_round = models.IntegerField(default=1)
    game_over = models.BooleanField(default=False)
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    wolfed_users = models.JSONField(default=list)
    round_status = models.CharField(max_length=50, default="waiting_to_start")  # waiting, in_progress, completed
