import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import MatchRoom, ChatMessage
from django.contrib.auth.models import User

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

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

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'id': msg_id,
                    'message': message,
                    'username': username
                }
            )

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        msg_id = event.get('id')

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'id': msg_id,
            'message': message,
            'username': username
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
        return [{'id': m.id, 'text': m.text, 'username': m.sender.username} for m in room.messages.order_by('timestamp')[:50]]

