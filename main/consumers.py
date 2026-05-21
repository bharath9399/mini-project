import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import MatchRoom, ChatMessage
from django.contrib.auth.models import User

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        # Verify user is a participant of this room
        is_participant = await self.check_participant()
        if not is_participant:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Send past messages
        messages = await self.get_past_messages()
        for msg in messages:
            await self.send(text_data=json.dumps({
                'id': msg['id'],
                'message': msg['text'],
                'username': msg['username'],
                'is_history': True
            }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'delete_message':
            message_id = data.get('message_id')
            success = await self.delete_message_db(message_id)
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message_deleted',
                        'message_id': message_id
                    }
                )
        elif action == 'clear_chat':
            success = await self.clear_chat_db()
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_cleared'
                    }
                )
        else:
            message = data['message']
            username = self.scope["user"].username

            # Save message to database
            msg_id = await self.save_message(message)
            timestamp_str = await self.get_message_timestamp(msg_id)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'id': msg_id,
                    'message': message,
                    'username': username,
                    'timestamp': timestamp_str
                }
            )

            # Send real-time notification to the other participant
            participants = await self.get_room_participants_and_subject()
            if participants:
                other_username, subject_name = participants
                await self.channel_layer.group_send(
                    f"user_notifications_{other_username}",
                    {
                        'type': 'chat_notification',
                        'room_id': self.room_id,
                        'sender': username,
                        'message': message,
                        'subject': subject_name
                    }
                )

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        msg_id = event.get('id')
        timestamp = event.get('timestamp', '')

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'id': msg_id,
            'message': message,
            'username': username,
            'timestamp': timestamp
        }))

    async def chat_message_deleted(self, event):
        message_id = event['message_id']
        await self.send(text_data=json.dumps({
            'action': 'delete_message',
            'message_id': message_id
        }))

    async def chat_cleared(self, event):
        await self.send(text_data=json.dumps({
            'action': 'clear_chat'
        }))

    @database_sync_to_async
    def save_message(self, message):
        room = MatchRoom.objects.get(id=self.room_id)
        msg = ChatMessage.objects.create(room=room, sender=self.scope["user"], text=message)
        return msg.id

    @database_sync_to_async
    def delete_message_db(self, message_id):
        try:
            room = MatchRoom.objects.get(id=self.room_id)
            if self.scope["user"] == room.student1 or self.scope["user"] == room.student2:
                msg = ChatMessage.objects.get(id=message_id, room=room)
                if msg.sender == self.scope["user"]:
                    msg.delete()
                    return True
        except Exception as e:
            print("Delete error:", e)
        return False

    @database_sync_to_async
    def clear_chat_db(self):
        try:
            room = MatchRoom.objects.get(id=self.room_id)
            if self.scope["user"] == room.student1 or self.scope["user"] == room.student2:
                room.messages.all().delete()
                return True
        except Exception as e:
            print("Clear error:", e)
        return False

    @database_sync_to_async
    def get_past_messages(self):
        room = MatchRoom.objects.get(id=self.room_id)
        return [{
            'id': m.id,
            'text': m.text,
            'username': m.sender.username,
            'timestamp': m.timestamp.isoformat() if m.timestamp else ''
        } for m in room.messages.order_by('timestamp')[:50]]

    @database_sync_to_async
    def get_message_timestamp(self, msg_id):
        try:
            return ChatMessage.objects.get(id=msg_id).timestamp.isoformat()
        except Exception:
            from django.utils import timezone
            return timezone.now().isoformat()

    @database_sync_to_async
    def check_participant(self):
        try:
            room = MatchRoom.objects.get(id=self.room_id)
            return self.scope["user"] == room.student1 or self.scope["user"] == room.student2
        except Exception:
            return False

    @database_sync_to_async
    def get_room_participants_and_subject(self):
        try:
            room = MatchRoom.objects.get(id=self.room_id)
            other_user = room.student2 if room.student1 == self.scope["user"] else room.student1
            subject_name = room.subject.name if room.subject else "General"
            return other_user.username, subject_name
        except Exception:
            return None


class NotificationConsumer(AsyncWebsocketConsumer):
    # Class-level dictionary to track active socket connections per user across multiple tabs
    active_users = {}  # { username: set(channel_name) }

    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.username = self.user.username
        self.notification_group = f"user_notifications_{self.username}"
        self.global_group = "global_notifications"

        # Join personal notification group
        await self.channel_layer.group_add(
            self.notification_group,
            self.channel_name
        )

        # Join global notifications group
        await self.channel_layer.group_add(
            self.global_group,
            self.channel_name
        )

        await self.accept()

        # Track connection in class-level dictionary
        if self.username not in NotificationConsumer.active_users:
            NotificationConsumer.active_users[self.username] = set()
        
        NotificationConsumer.active_users[self.username].add(self.channel_name)

        # If this is the user's first active tab/connection, set online status and broadcast
        if len(NotificationConsumer.active_users[self.username]) == 1:
            await self.update_online_status(True)
            user_data = await self.get_user_details()
            await self.channel_layer.group_send(
                self.global_group,
                {
                    'type': 'status_update',
                    'username': self.username,
                    'is_online': True,
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'default_subject': user_data['default_subject'],
                    'default_level': user_data['default_level'],
                    'subjects': user_data['subjects'],
                    'subject_levels': user_data['subject_levels']
                }
            )

    async def disconnect(self, close_code):
        if hasattr(self, 'username'):
            # Remove connection
            if self.username in NotificationConsumer.active_users:
                NotificationConsumer.active_users[self.username].discard(self.channel_name)
                
                # If no more active tabs/connections exist for this user, mark offline and broadcast
                if len(NotificationConsumer.active_users[self.username]) == 0:
                    NotificationConsumer.active_users.pop(self.username, None)
                    await self.update_online_status(False)
                    await self.channel_layer.group_send(
                        self.global_group,
                        {
                            'type': 'status_update',
                            'username': self.username,
                            'is_online': False
                        }
                    )

            # Leave groups
            await self.channel_layer.group_discard(
                self.notification_group,
                self.channel_name
            )
            await self.channel_layer.group_discard(
                self.global_group,
                self.channel_name
            )

    async def chat_notification(self, event):
        # Forward the notification message to the client WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_notification',
            'room_id': event['room_id'],
            'sender': event['sender'],
            'message': event['message'],
            'subject': event['subject']
        }))

    async def status_update(self, event):
        # Forward status change event to the client WebSocket
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'username': event['username'],
            'is_online': event['is_online'],
            'first_name': event.get('first_name'),
            'last_name': event.get('last_name'),
            'default_subject': event.get('default_subject'),
            'default_level': event.get('default_level'),
            'subjects': event.get('subjects'),
            'subject_levels': event.get('subject_levels')
        }))

    @database_sync_to_async
    def get_user_details(self):
        try:
            user = self.user
            first_name = user.first_name or user.username.capitalize()
            last_name = user.last_name or ""
            
            # Retrieve subject selections
            profile = user.profile
            selections = profile.subject_selections.all()
            subj_list = [sel.subject.name for sel in selections]
            subj_str = ",".join(subj_list)
            
            lvl_list = [f"{sel.subject.name.lower()}:{sel.get_level_display()}" for sel in selections]
            lvl_str = ",".join(lvl_list)
            
            first_sel = selections.first()
            default_subject = first_sel.subject.name if first_sel else "General"
            default_level = first_sel.get_level_display() if first_sel else "Beginner"
            
            return {
                'first_name': first_name,
                'last_name': last_name,
                'default_subject': default_subject,
                'default_level': default_level,
                'subjects': subj_str,
                'subject_levels': lvl_str
            }
        except Exception as e:
            print(f"Error fetching user details in socket: {e}")
            return {
                'first_name': self.username.capitalize(),
                'last_name': '',
                'default_subject': 'General',
                'default_level': 'Beginner',
                'subjects': '',
                'subject_levels': ''
            }

    @database_sync_to_async
    def update_online_status(self, is_online):
        try:
            profile = self.user.profile
            profile.is_online = is_online
            profile.save()
        except Exception as e:
            print(f"Error updating online status for {self.username}: {e}")


