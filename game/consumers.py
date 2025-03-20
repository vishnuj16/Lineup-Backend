# consumers.py
import json
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from .models import Room, Player, Round, WolfList
from django.contrib.auth.models import User
import random
import asyncio

class GameLobbyConsumer(WebsocketConsumer):
    """
    Consumer for handling game lobby events (game start notification)
    """
    def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group_name = f'lobby_{self.room_code}'
        
        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )
        
        self.accept()
    
    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )
    
    # Receive message from WebSocket
    def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'game_start':
            # Send message to room group
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'game_start_message',
                    'message': 'Game is starting!'
                }
            )
        
        if message_type == 'player_joined':
            player_id = data.get('player')
            try:
                player = Player.objects.get(id=player_id)
                # Send message to room group
                async_to_sync(self.channel_layer.group_send)(
                    self.room_group_name,
                    {
                        'type': 'player_joined',
                        'player': player.user.username
                    }
                )
            except Player.DoesNotExist:
                pass

    def player_joined(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps({
            'type': 'player_joined',
            'player': event['player']
        }))
    
    # Receive message from room group
    def game_start_message(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps({
            'type': 'game_start',
            'message': event['message']
        }))


class GameplayConsumer(WebsocketConsumer):
    """
    Consumer for handling actual gameplay events
    """
    def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group_name = f'game_{self.room_code}'
        self.user = self.scope['user']
        
        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )
        
        self.accept()
    
    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )
    
    # Receive message from WebSocket
    def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'start_round':
            round_number = data.get('round_number')
            self.start_round(round_number)
        
        elif message_type == 'wolf_order':
            order = data.get('order')
            round_number = data.get('round_number')
            self.submit_wolf_order(order, round_number)
        
        elif message_type == 'pack_order':
            order = data.get('order')
            round_number = data.get('round_number')
            self.submit_pack_order(order, round_number)
    
    def start_round(self, round_number):
        try:
            room = Room.objects.get(code=self.room_code)
            # Check if the user is the host
            if room.host != self.user:
                self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Only the host can start the round'
                }))
                return
            
            current_round = Round.objects.get(room=room, round_number=round_number)
            
            # Select a wolf who hasn't been a wolf yet
            wolf_list, _ = WolfList.objects.get_or_create(room=room)
            wolfed_users = wolf_list.wolfed_users
            
            players = list(room.players.all())
            eligible_players = [player for player in players if player.user.id not in wolfed_users]
            
            # If all players have been wolf, reset the wolf list
            if not eligible_players:
                wolf_list.wolfed_users = []
                wolf_list.save()
                eligible_players = players
            
            chosen_player = random.choice(eligible_players)
            current_round.wolf = chosen_player.user
            
            # Update wolf list
            wolfed_users.append(chosen_player.user.id)
            wolf_list.wolfed_users = wolfed_users
            wolf_list.save()
            
            # Get a question for the round
            questions = [
                "Rank these foods from most to least delicious",
                "Rank these movies from best to worst",
                "Rank these vacation destinations from most to least desirable",
                "Rank these sports from most to least exciting",
                "Rank these animals from most to least dangerous"
            ]
            current_round.question = random.choice(questions)
            current_round.save()
            
            # Send message to room group
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'round_start_message',
                    'round_number': round_number,
                    'wolf_id': current_round.wolf.id,
                    'question': current_round.question
                }
            )
            
            # Start wolf timer (2 minutes)
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'wolf_timer_message',
                    'round_number': round_number,
                    'time': 120  # 2 minutes in seconds
                }
            )
            
        except Room.DoesNotExist:
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Room not found'
            }))
        except Round.DoesNotExist:
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Round not found'
            }))
    
    def submit_wolf_order(self, order, round_number):
        try:
            room = Room.objects.get(code=self.room_code)
            current_round = Round.objects.get(room=room, round_number=round_number)
            
            # Check if the user is the wolf
            if current_round.wolf != self.user:
                self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Only the wolf can submit the order'
                }))
                return
            
            # Save the wolf's ranking
            current_round.wolf_ranking = order
            current_round.save()
            
            # Notify everyone that the wolf has submitted their order
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'wolf_order_message',
                    'round_number': round_number,
                    'order': order
                }
            )
            
        except Room.DoesNotExist:
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Room not found'
            }))
        except Round.DoesNotExist:
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Round not found'
            }))
    
    def submit_pack_order(self, order, round_number):
        try:
            room = Room.objects.get(code=self.room_code)
            current_round = Round.objects.get(room=room, round_number=round_number)
            
            # Check if the user is the host (or the lowest scoring player if host is wolf)
            valid_submitter = False
            if room.host == self.user and current_round.wolf != self.user:
                valid_submitter = True
            elif room.host == current_round.wolf:
                # Find the lowest scoring player who isn't the wolf
                players = room.players.exclude(user=current_round.wolf).order_by('score')
                if players.exists() and players.first().user == self.user:
                    valid_submitter = True
            
            if not valid_submitter:
                self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'You are not authorized to submit the pack order'
                }))
                return
            
            # Save the pack's ranking
            current_round.pack_ranking = order
            
            # Calculate score based on similarity between wolf and pack rankings
            wolf_ranking = current_round.wolf_ranking
            pack_score = 0
            
            # Simple scoring: +1 for each matching position
            for item, position in order.items():
                if wolf_ranking.get(item) == position:
                    pack_score += 1
            
            current_round.pack_score = pack_score
            current_round.save()
            
            # Each pack member gets points equal to the pack score
            if pack_score > 0:
                for player in room.players.exclude(user=current_round.wolf):
                    player.score += pack_score
                    player.save()
            
            # Wolf never gets points
            
            # Notify everyone about the results
            async_to_sync(self.channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'round_result_message',
                    'round_number': round_number,
                    'wolf_order': wolf_ranking,
                    'pack_order': order,
                    'pack_score': pack_score
                }
            )
            
        except Room.DoesNotExist:
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Room not found'
            }))
        except Round.DoesNotExist:
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Round not found'
            }))
    
    # Receive message from room group
    def round_start_message(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps({
            'type': 'round_start',
            'round_number': event['round_number'],
            'wolf_id': event['wolf_id'],
            'question': event['question']
        }))
    
    def wolf_timer_message(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps({
            'type': 'wolf_timer',
            'round_number': event['round_number'],
            'time': event['time']
        }))
    
    def wolf_order_message(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps({
            'type': 'wolf_order',
            'round_number': event['round_number'],
            'order': event['order']
        }))
    
    def round_result_message(self, event):
        # Send message to WebSocket
        self.send(text_data=json.dumps({
            'type': 'round_result',
            'round_number': event['round_number'],
            'wolf_order': event['wolf_order'],
            'pack_order': event['pack_order'],
            'pack_score': event['pack_score']
        }))