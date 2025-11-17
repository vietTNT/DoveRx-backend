from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
import json
import asyncio
import traceback
from .models import Conversation, Message
from .serializers import MessageSerializer
from accounts.models import UserStatus

class ChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer xử lý chat real-time giữa 2 người
    """
    
    async def connect(self):
        """Được gọi khi client mở WebSocket connection"""
        try:
            self.user = self.scope.get('user', AnonymousUser())
            
            if not self.user.is_authenticated:
                print("❌ [ChatConsumer] Unauthenticated user, closing connection")
                await self.close(code=4001)
                return
            
            self.user_group_name = f'user_{self.user.id}'
            
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            
            await self.set_user_online(True)
            await self.accept()
            
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': f'Connected as {self.user.username}',
                'user_id': self.user.id
            }))
            
            print(f"✅ Chat WebSocket connected: {self.user.username} (ID: {self.user.id})")
            
        except Exception as e:
            print(f"❌ Error in connect: {e}")
            print(traceback.format_exc())
            await self.close(code=4003)
    
    async def disconnect(self, close_code):
        """Được gọi khi client đóng WebSocket"""
        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.set_user_online(False)
        
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        
        print(f"🔌 Chat WebSocket disconnected: {self.user.username if hasattr(self, 'user') else 'Unknown'} (code: {close_code})")
    
    async def receive(self, text_data):
        """Được gọi khi nhận tin nhắn từ client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            print(f"📩 [ChatConsumer] Nhận từ {self.user.username}: type={message_type}, data={data}")
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp', '')
                }))
                return
            
            if message_type == 'send_message':
                print(f"🔵 [ChatConsumer] Calling handle_send_message...")
                await self.handle_send_message(data)
                return
            
            if message_type == 'typing':
                await self.handle_typing(data)
                return
            
            if message_type == 'mark_read':
                await self.handle_mark_read(data)
                return
            
            print(f"⚠️ [ChatConsumer] Unknown message type: {message_type}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Unknown message type: {message_type}'
            }))
                
        except json.JSONDecodeError as e:
            print(f"❌ [ChatConsumer] JSON decode error: {e}")
        except Exception as e:
            print(f"❌ [ChatConsumer] Exception: {e}")
            print(traceback.format_exc())
    
    # ==================== MESSAGE HANDLERS ====================
    
    async def handle_send_message(self, data):
        """Xử lý khi user gửi tin nhắn"""
        try:
            conversation_id = data.get('conversation_id')
            text = data.get('text', '').strip()
            
            print(f"🔵 [handle_send_message] START")
            print(f"   conversation_id: {conversation_id}")
            print(f"   text: '{text}'")
            print(f"   user: {self.user.username} (ID: {self.user.id})")
            
            if not conversation_id or not text:
                print(f"❌ [handle_send_message] Missing data")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Thiếu conversation_id hoặc text'
                }))
                return
            
            message = await self.save_message(conversation_id, text)
            
            if not message:
                print(f"❌ [handle_send_message] save_message returned None")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Không thể lưu tin nhắn'
                }))
                return
            
            print(f"✅ [handle_send_message] Message saved: id={message.get('id')}")
            
            other_user_id = await self.get_other_user_id(conversation_id)
            print(f"🔵 [handle_send_message] other_user_id={other_user_id}")
            
            if not other_user_id:
                print(f"❌ [handle_send_message] Cannot find other_user_id")
                return
            
            group_name = f'user_{other_user_id}'
            print(f"📤 [handle_send_message] Broadcasting to group: {group_name}")
            
            await self.channel_layer.group_send(
                group_name,
                {
                    'type': 'new_message',
                    'message': message
                }
            )
            print(f"✅ [handle_send_message] Broadcast sent")
            
            await self.send(text_data=json.dumps({
                'type': 'message_sent',
                'message': message
            }))
            print(f"✅ [handle_send_message] COMPLETED")
            
        except Exception as e:
            print(f"❌ [handle_send_message] Exception: {e}")
            print(traceback.format_exc())
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Lỗi server: {str(e)}'
            }))
    
    async def handle_typing(self, data):
        """Xử lý typing indicator"""
        try:
            conversation_id = data.get('conversation_id')
            is_typing = data.get('is_typing', True)
            
            print(f"⌨️ [handle_typing] user={self.user.username}, conversation={conversation_id}, is_typing={is_typing}")
            
            if not conversation_id:
                return
            
            other_user_id = await self.get_other_user_id(conversation_id)
            
            if other_user_id:
                group_name = f'user_{other_user_id}'
                print(f"📤 [handle_typing] Broadcasting to {group_name}")
                
                await self.channel_layer.group_send(
                    group_name,
                    {
                        'type': 'user_typing',
                        'conversation_id': conversation_id,
                        'user_id': self.user.id,
                        'user_name': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username,
                        'is_typing': is_typing
                    }
                )
        except Exception as e:
            print(f"❌ [handle_typing] Error: {e}")
            print(traceback.format_exc())
    
    async def handle_mark_read(self, data):
        """Đánh dấu tin nhắn đã đọc"""
        try:
            conversation_id = data.get('conversation_id')
            
            print(f"👁️ [handle_mark_read] user={self.user.username}, conversation={conversation_id}")
            
            if not conversation_id:
                return
            
            await self.mark_messages_as_read(conversation_id)
            
            other_user_id = await self.get_other_user_id(conversation_id)
            
            if other_user_id:
                await self.channel_layer.group_send(
                    f'user_{other_user_id}',
                    {
                        'type': 'messages_read',
                        'conversation_id': conversation_id,
                        'user_id': self.user.id
                    }
                )
        except Exception as e:
            print(f"❌ [handle_mark_read] Error: {e}")
    
    # ==================== CHANNEL LAYER HANDLERS ====================
    
    async def new_message(self, event):
        """Gửi tin nhắn mới đến client"""
        try:
            print(f"📨 [new_message] CALLED - Sending to client...")
            print(f"   event: {event}")
            
            await self.send(text_data=json.dumps({
                'type': 'new_message',
                'message': event['message']
            }))
            
            print(f"✅ [new_message] Sent successfully")
        except Exception as e:
            print(f"❌ [new_message] Error: {e}")
            print(traceback.format_exc())
    
    async def user_typing(self, event):
        """Gửi typing event xuống client"""
        try:
            await self.send(text_data=json.dumps({
                'type': 'user_typing',
                'conversation_id': event['conversation_id'],
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))
        except Exception as e:
            print(f"❌ [user_typing] Error: {e}")
    
    async def messages_read(self, event):
        """Gửi read status xuống client"""
        try:
            await self.send(text_data=json.dumps({
                'type': 'messages_read',
                'conversation_id': event['conversation_id'],
                'user_id': event['user_id']
            }))
        except Exception as e:
            print(f"❌ [messages_read] Error: {e}")
    
    # ==================== DATABASE OPERATIONS ====================
    
    @database_sync_to_async
    def save_message(self, conversation_id, text):
        """Lưu tin nhắn vào database"""
        try:
            print(f"🔵 [save_message] START - conversation_id={conversation_id}, user_id={self.user.id}")
            
            conversation = Conversation.objects.filter(
                id=conversation_id,
                participants=self.user
            ).first()
            
            if not conversation:
                print(f"❌ [save_message] Conversation not found")
                return None
            
            print(f"✅ [save_message] Found conversation: {conversation}")
            print(f"   Participants: {[p.username for p in conversation.participants.all()]}")
            
            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                text=text
            )
            
            print(f"✅ [save_message] Message created in DB: id={message.id}")
            
            conversation.save()
            
            # ✅ Build avatar URL
            # avatar_url = None
            # if self.user.avatar:
            #     # Lấy base URL từ settings
            #     from django.conf import settings
            #     base_url = settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000'
            #     avatar_url = f"{base_url}{self.user.avatar.url}"
            avatar_url = None
            if self.user.avatar and hasattr(self.user.avatar, "url"):
                avatar_url = self.user.avatar.url   # Cloudinary trả đúng URL HTTPS

            result = {
                'id': message.id,
                'conversation': message.conversation.id,
                'sender': {
                    'id': self.user.id,
                    'username': self.user.username,
                    'first_name': self.user.first_name,
                    'last_name': self.user.last_name,
                    'avatar': avatar_url,
                    'name': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
                },
                'text': message.text,
                'created_at': message.created_at.isoformat(),
                'is_read': message.is_read
            }
            
            print(f"✅ [save_message] Serialized message: {result}")
            return result
            
        except Exception as e:
            print(f"❌ [save_message] Exception: {e}")
            print(traceback.format_exc())
            return None
    
    @database_sync_to_async
    def get_other_user_id(self, conversation_id):
        """Lấy ID người nhận"""
        try:
            conversation = Conversation.objects.filter(
                id=conversation_id,
                participants=self.user
            ).prefetch_related('participants').first()
            
            if not conversation:
                print(f"❌ [get_other_user_id] Conversation not found")
                return None
            
            participants = list(conversation.participants.all())
            print(f"🔵 [get_other_user_id] Participants: {[p.username for p in participants]}")
            
            for participant in participants:
                if participant.id != self.user.id:
                    print(f"✅ [get_other_user_id] Found other user: {participant.username} (ID: {participant.id})")
                    return participant.id
            
            print(f"❌ [get_other_user_id] No other user found")
            return None
            
        except Exception as e:
            print(f"❌ [get_other_user_id] Exception: {e}")
            print(traceback.format_exc())
            return None
    
    @database_sync_to_async
    def mark_messages_as_read(self, conversation_id):
        """Đánh dấu tin nhắn đã đọc"""
        try:
            conversation = Conversation.objects.filter(
                id=conversation_id,
                participants=self.user
            ).first()
            
            if not conversation:
                return
            
            count = Message.objects.filter(
                conversation_id=conversation_id,
                is_read=False
            ).exclude(sender=self.user).update(is_read=True)
            
            print(f"✅ [mark_messages_as_read] Marked {count} messages as read")
            
        except Exception as e:
            print(f"❌ [mark_messages_as_read] Error: {e}")
    
    @database_sync_to_async
    def set_user_online(self, is_online):
        """
        Cập nhật trạng thái online/offline của user
        
        Args:
            is_online (bool): True = online, False = offline
        """
        try:
            status, created = UserStatus.objects.get_or_create(user=self.user)
            status.is_online = is_online
            status.save()
            
            print(f"✅ [set_user_online] User {self.user.username} status: {'online' if is_online else 'offline'}")
        except Exception as e:
            print(f"❌ [set_user_online] Error: {e}")
            print(traceback.format_exc())