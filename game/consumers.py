# consumers.py
import json
from asgiref.sync import async_to_sync, sync_to_async
from channels.generic.websocket import WebsocketConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, Player, Round, Game
from django.contrib.auth.models import User
import random
import asyncio

class GameLobbyConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        print(f"User connecting: {self.user}")

        if self.user.is_anonymous:
            print("User is anonymous, closing connection.")
            await self.close()
            return

        print("Connection accepted!")
        await self.accept()

        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group_name = f'lobby_{self.room_code}'
        
        # Join room group (Await directly)
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Send notification that the user has joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'player_joined',
                'player': self.user.username
            }
        )
        
        # After join notification, send updated player count to everyone
        players = await self.get_players_in_room()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'player_count',
                'count': len(players)
            }
        )
    
    @database_sync_to_async
    def get_players_in_room(self):
        """Get list of players in the current room"""
        try:
            room = Room.objects.get(code=self.room_code)
            return list(room.players.all())
        except Room.DoesNotExist:
            return []
    
    async def disconnect(self, close_code):
        if not hasattr(self, 'user') or self.user.is_anonymous:
            return
        
        # Leave room group (Await directly)
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Notify others that player has left
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'player_left',
                'player': self.user.username
            }
        )

    async def receive_json(self, content):
        message_type = content.get('type')
        print(f"Received message: {content}")
        
        if message_type == 'game_start':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_start_message',
                    'message': 'Game is starting!'
                }
            )
        
        # Use receive_json instead of receive for better JSON handling
        elif message_type == 'player_joined':
            player_id = content.get('player')
            player = await self.get_player(player_id)
            if player:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'player_joined',
                        'player': player
                    }
                )

    @database_sync_to_async
    def get_player(self, player_id):
        try:
            player = Player.objects.get(id=player_id)
            return player.user.username
        except Player.DoesNotExist:
            return None

    # Handler for player_joined messages
    async def player_joined(self, event):
        # Send message to WebSocket
        await self.send_json({
            'type': 'player_joined',
            'player': event['player']
        })
    
    async def player_left(self, event):
        # Send message to WebSocket when a player leaves
        await self.send_json({
            'type': 'player_left',
            'player': event['player']
        })
    
    async def player_count(self, event):
        # Send player count to WebSocket
        await self.send_json({
            'type': 'player_count',
            'count': event['count']
        })
    
    # Receive message from room group
    async def game_start_message(self, event):
        # Send message to WebSocket
        await self.send_json({
            'type': 'game_start',
            'message': event['message']
        })


class GameplayConsumer(AsyncJsonWebsocketConsumer):
    
    async def connect(self):
        self.user = self.scope["user"]
        print(f"User connecting: {self.user}")

        if self.user.is_anonymous:
            print("User is anonymous, closing connection.")
            await self.close()
            return

        print("Connection accepted!")
        await self.accept()

        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group_name = f'lobby_{self.room_code}'
        
        # Join room group (Await directly)
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
    
    async def disconnect(self, close_code):
        if not hasattr(self, 'user') or self.user.is_anonymous:
            return
        
        # Leave room group (Await directly)
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    
    async def receive_json(self, content):
        message_type = content.get('type')
        print("Received message: ", content)
        
        if message_type == 'start_round':
            round_number = content.get('round_number')
            await self.start_round(round_number)
        
        elif message_type == 'change_status':
            status = content.get('status')
            round_number = content.get('round_number')
            await self.change_status(status, round_number)
        
        elif message_type == 'wolf_order':
            order = content.get('order')
            round_number = content.get('round_number')
            await self.submit_wolf_order(order, round_number)
        
        elif message_type == 'pack_order':
            order = content.get('order')
            round_number = content.get('round_number')
            await self.submit_pack_order(order, round_number)

        else:
            print("Unknown message type:", message_type)
            # Handle unknown message type if necessary
            pass
    
    @database_sync_to_async
    def get_room(self, room_code):
        return Room.objects.get(code=room_code)
    
    @database_sync_to_async
    def get_round(self, room, round_number):
        return Round.objects.get(room=room, round_number=round_number)
    
    @database_sync_to_async
    def get_rounds(self, room):
        return list(Round.objects.filter(room=room))
    
    @database_sync_to_async
    def get_game(self, room):
        return Game.objects.get(room=room)
    
    @database_sync_to_async
    def save_round(self, current_round):
        current_round.save()
    
    @database_sync_to_async
    def save_game(self, game):
        game.save()
    
    @database_sync_to_async
    def get_eligible_players(self, room, wolfed_users):
        players = list(room.players.all())
        return [player for player in players if player.user.id not in wolfed_users]
    
    @database_sync_to_async
    def get_all_players(self, room):
        return list(room.players.all())
    
    @database_sync_to_async
    def get_all_players_count(self, room):
        return room.players.count()
    
    @database_sync_to_async
    def get_players_exclude_wolf(self, room, wolf_user):
        return list(room.players.exclude(user=wolf_user).order_by('score'))
    
    @database_sync_to_async
    def update_player_scores(self, room, wolf_user, pack_score):
        for player in room.players.exclude(user=wolf_user):
            player.score += pack_score
            player.save()
    
    @database_sync_to_async
    def is_user_host(self, room, user):
        return room.host == user
    
    @database_sync_to_async
    def check_valid_submitter(self, room, current_round, user):
        # Check if the user is the host (or the lowest scoring player if host is wolf)
        if room.host == user and current_round.wolf != user:
            return True
        elif room.host == current_round.wolf:
            # Find the lowest scoring player who isn't the wolf
            players = list(room.players.exclude(user=current_round.wolf).order_by('score'))
            if players and players[0].user == user:
                return True
        return False
    
    @database_sync_to_async
    def create_wolf_rankings(self, current_round, room, wolfed_users):
        # Get players
        players = list(room.players.all())
        eligible_players = [player for player in players if player.user.id not in wolfed_users]
        
        # If all players have been wolf, reset the wolf list
        if not eligible_players:
            return [], players
        
        return eligible_players, None
    
    async def start_round(self, round_number):
        try:
            print("meow")
            room = await self.get_room(self.room_code)
            
            # Check if the user is the host - use our async helper method
            is_host = await self.is_user_host(room, self.user)
            if not is_host:
                print("User is not the host, cannot start round.")
                await self.send_json({
                    'type': 'error',
                    'message': 'Only the host can start the round'
                })
                return
            
            print("hi")
            game = await self.get_game(room)
            
            # Check if the game should end
            players_count = await self.get_all_players_count(room)
            all_rounds_complete = await self.check_all_rounds_complete(room, players_count)
            
            if round_number > players_count and all_rounds_complete:
                # Game is ending, collect statistics
                game_stats = await self.collect_game_statistics(room)
                
                # Update game status
                game.round_status = "game_ended"
                await self.save_game(game)
                
                # Send game end message to all clients
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_end_message',
                        'statistics': game_stats
                    }
                )
                print("Game has ended! Statistics sent to all players")
                return
            
            current_round = await self.get_round(room, round_number)
            print("done")
            wolfed_users = game.wolfed_users
            
            eligible_players, all_players = await self.create_wolf_rankings(current_round, room, wolfed_users)
            print("noo")
            
            # If all players have been wolf, reset the wolf list
            if not eligible_players:
                game.wolfed_users = []
                await self.save_game(game)
                eligible_players = await self.get_all_players(room)
            elif all_players:
                eligible_players = all_players
            
            chosen_player = random.choice(eligible_players)
            current_round.wolf = chosen_player.user

            print("Chosen player: ", chosen_player.user.username)
            await self.save_round(current_round)
            
            # Update wolf list
            wolfed_users.append(chosen_player.user.id)
            game.wolfed_users = wolfed_users

            game.round_status = "wolf_selection"
            print("ornt : ", game)
            await self.save_game(game)
            
            # Get a question for the round
            questions = [
                "Rank these foods from most to least delicious",
                "Rank these movies from best to worst",
                "Rank these vacation destinations from most to least desirable",
                "Rank these sports from most to least exciting",
                "Rank these animals from most to least dangerous"
            ]
            current_round.question = random.choice(questions)
            await self.save_round(current_round)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'round_start_message',
                    'round_number': round_number,
                    'wolf_id': current_round.wolf.username,
                    'question': current_round.question
                }
            )

            print("Round started!", game, current_round, chosen_player.user.username)
            
            # Start wolf timer (2 minutes)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'wolf_timer_message',
                    'round_number': round_number,
                    'time': 120  # 2 minutes in seconds
                }
            )
            
        except Room.DoesNotExist:
            await self.send_json({
                'type': 'error',
                'message': 'Room not found'
            })
        except Round.DoesNotExist:
            await self.send_json({
                'type': 'error',
                'message': 'Round not found'
            })

    # Helper methods needed for game ending logic
    async def get_player_count(self, room):
        """Get the number of players in the room"""
        return await Player.objects.filter(room=room).count()

    async def check_all_rounds_complete(self, room, player_count):
        """Check if all rounds have values and scores populated"""
        rounds = await self.get_rounds(room)
        
        # Check if we have the expected number of rounds and they all have scores
        if len(rounds) < player_count:
            return False
        
        for round_obj in rounds:
            # Check if this round has scores and values populated
            if round_obj.wolf_ranking is None or round_obj.pack_ranking is None:
                return False
        
        return True

    async def collect_game_statistics(self, room):
        """Collect statistics for the game"""
        players = await Player.objects.filter(room=room).all()
        rounds = await Round.objects.filter(room=room).all()
        
        # Initialize statistics dictionary
        statistics = {
            'players': {},
            'round_data': [],
            'winners': [],
            'total_rounds': len(rounds)
        }
        
        # Collect individual player scores
        for player in players:
            player_stats = {
                'username': player.user.username,
                'total_score': player.score,
                'round_scores': [],
                'rounds_as_wolf': 0,
            }
            for round_obj in rounds:
                        
                # Track if player was wolf
                if round_obj.wolf and round_obj.wolf.id == player.user.id:
                    player_stats['rounds_as_wolf'] += 1
                else:
                    player_stats['round_scores'].append(round_obj.pack_score)
               
        
        # Collect round data
        for round_obj in rounds:
            round_data = {
                'round_number': round_obj.round_number,
                'question': round_obj.question,
                'wolf': round_obj.wolf.username if round_obj.wolf else None,
                'scores': round_obj.pack_score
            }
            statistics['round_data'].append(round_data)
        
        max_score = max([player.score for player in players])
        winners = [player.user.username for player in players if player.score == max_score]
        statistics['winners'] = winners
        statistics['players'] = {player.user.username: player_stats for player, player_stats in zip(players, statistics['players'].values())}
        
        return statistics

    # You'll also need to add a handler for the game_end_message
    async def game_end_message(self, event):
        """Send game end message to WebSocket"""
        await self.send_json({
            'type': 'game_end',
            'statistics': event['statistics']
        })

    async def change_status(self, status, round_number):
        try:
            room = await self.get_room(self.room_code)
            game = await self.get_game(room)

            game.round_status = status
            await self.save_game(game)
            
            # Notify everyone about the status change
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'status_change_message',
                    'round_number': round_number,
                    'status': status
                }
            )
            
        except Room.DoesNotExist:
            await self.send_json({
                'type': 'error',
                'message': 'Room not found'
            })
    
    @database_sync_to_async
    def get_wolf_from_round(self, current_round):
        """Get the wolf user from a round object"""
        # Force the related object to be loaded in the sync context
        return current_round.wolf
    
    @database_sync_to_async
    def get_first_user(self, players):
        return players[0].user if players else None

    async def submit_wolf_order(self, order, round_number):
        try:
            room = await self.get_room(self.room_code)
            current_round = await self.get_round(room, round_number)
            game = await self.get_game(room)
            
            # Get the wolf user properly in async context
            wolf_user = await self.get_wolf_from_round(current_round)
            
            # Now get players excluding the wolf
            players = await self.get_players_exclude_wolf(room, wolf_user)
            
            submitter = await self.get_first_user(players)

            if not submitter:
                await self.send_json({
                    'type': 'error',
                    'message': 'No players available to submit the order'
                })
                return
            
            # Check if the user is the wolf
            if wolf_user != self.user:
                await self.send_json({
                    'type': 'error',
                    'message': 'Only the wolf can submit the order'
                })
                return
            
            # Save the wolf's ranking
            current_round.wolf_ranking = order
            await self.save_round(current_round)

            game.round_status = "pack_selection"
            await self.save_game(game)
            
            # Notify everyone that the wolf has submitted their order
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'wolf_order_message',
                    'round_number': round_number,
                    'submitter': submitter.username,
                }
            )
            
        except Room.DoesNotExist:
            await self.send_json({
                'type': 'error',
                'message': 'Room not found'
            })
        except Round.DoesNotExist:
            await self.send_json({
                'type': 'error',
                'message': 'Round not found'
            })
        except Game.DoesNotExist:
            await self.send_json({
                'type': 'error',
                'message': 'Game not found'
            })
    
    async def submit_pack_order(self, order, round_number):
        try:
            room = await self.get_room(self.room_code)
            current_round = await self.get_round(room, round_number)
            game = await self.get_game(room)
            
            # Check if user is valid submitter using our async helper
            valid_submitter = await self.check_valid_submitter(room, current_round, self.user)
            
            if not valid_submitter:
                await self.send_json({
                    'type': 'error',
                    'message': 'You are not authorized to submit the pack order'
                })
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
            await self.save_round(current_round)
            
            # Each pack member gets points equal to the pack score
            if pack_score > 0:
                await self.update_player_scores(room, current_round.wolf, pack_score)
            
            # Wolf never gets points

            game.round_status = "round_completed"
            game.current_round += 1
            game.round_status = "waiting_to_start"
            await self.save_game(game)
            
            wolf_order = await self.get_usernames(current_round.wolf_ranking)
            pack_order = await self.get_usernames(current_round.pack_ranking)
            # Notify everyone about the results
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'round_result_message',
                    'round_number': round_number,
                    'wolf_order': wolf_order,
                    'pack_order': pack_order,
                    'pack_score': pack_score
                }
            )
            
        except Room.DoesNotExist:
            await self.send_json({
                'type': 'error',
                'message': 'Room not found'
            })
        except Round.DoesNotExist:
            await self.send_json({
                'type': 'error',
                'message': 'Round not found'
            })
    
    @database_sync_to_async
    def get_usernames(self, orders):
        """Get usernames from orders"""
        result = {}
        for item, position in orders.items():
            player = Player.objects.get(id=item)
            result[item] = player.user.username
        return result


    # Message handlers
    async def round_start_message(self, event):
        await self.send_json({
            'type': 'round_start',
            'round_number': event['round_number'],
            'wolf_id': event['wolf_id'],
            'question': event['question']
        })
    
    async def wolf_timer_message(self, event):
        await self.send_json({
            'type': 'wolf_timer',
            'round_number': event['round_number'],
            'time': event['time']
        })
    
    async def wolf_order_message(self, event):
        await self.send_json({
            'type': 'wolf_order',
            'round_number': event['round_number'],
            'submitter': event['submitter']
        })
    
    async def round_result_message(self, event):
        await self.send_json({
            'type': 'round_result',
            'round_number': event['round_number'],
            'wolf_order': event['wolf_order'],
            'pack_order': event['pack_order'],
            'pack_score': event['pack_score']
        })
    
    async def status_change_message(self, event):
        await self.send_json({
            'type': 'status_change',
            'round_number': event['round_number'],
            'status': event['status']
        })