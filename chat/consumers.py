from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
import json
import traceback
from .models import Conversation, Message
from accounts.models import UserStatus

class ChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer xử lý chat real-time giữa 2 người
    """
    
    async def connect(self):
        try:
            self.user = self.scope.get('user', AnonymousUser())
            
            if not self.user.is_authenticated:
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
            
        except Exception as e:
            print(f"❌ Error in connect: {e}")
            await self.close(code=4003)
    
    async def disconnect(self, close_code):
        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.set_user_online(False)
        
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
                return
            
            if message_type == 'send_message':
                await self.handle_send_message(data)
                return
            
            if message_type == 'typing':
                await self.handle_typing(data)
                return
            
            if message_type == 'mark_read':
                await self.handle_mark_read(data)
                return
                
        except Exception as e:
            print(f"❌ [ChatConsumer] Exception: {e}")
    
    async def handle_send_message(self, data):
        try:
            conversation_id = data.get('conversation_id')
            text = data.get('text', '').strip()
            attachment = data.get('attachment', None)

            if not conversation_id or (not text and not attachment):
                return
            
            # Gọi hàm save_message
            message_data = await self.save_message(conversation_id, text, attachment)
            
            if not message_data:
                return
            
            # Gửi cho người nhận
            other_user_id = await self.get_other_user_id(conversation_id)
            if other_user_id:
                await self.channel_layer.group_send(
                    f'user_{other_user_id}',
                    {
                        'type': 'new_message',
                        'message': message_data
                    }
                )
            
            # Gửi confirm lại cho người gửi
            await self.send(text_data=json.dumps({
                'type': 'message_sent',
                'message': message_data
            }))
            
        except Exception as e:
            print(f"❌ Handle send message error: {e}")

    # ... (Giữ nguyên handle_typing, handle_mark_read, new_message, user_typing, messages_read) ...
    async def handle_typing(self, data):
        try:
            conversation_id = data.get('conversation_id')
            is_typing = data.get('is_typing', True)
            if not conversation_id: return
            other_user_id = await self.get_other_user_id(conversation_id)
            if other_user_id:
                await self.channel_layer.group_send(f'user_{other_user_id}', {
                    'type': 'user_typing', 'conversation_id': conversation_id,
                    'user_id': self.user.id, 'is_typing': is_typing
                })
        except: pass

    async def handle_mark_read(self, data):
        try:
            conversation_id = data.get('conversation_id')
            if not conversation_id: return
            await self.mark_messages_as_read(conversation_id)
            other_user_id = await self.get_other_user_id(conversation_id)
            if other_user_id:
                await self.channel_layer.group_send(f'user_{other_user_id}', {
                    'type': 'messages_read', 'conversation_id': conversation_id, 'user_id': self.user.id
                })
        except: pass

    async def new_message(self, event):
        await self.send(text_data=json.dumps({'type': 'new_message', 'message': event['message']}))

    async def user_typing(self, event):
        await self.send(text_data=json.dumps(event))

    async def messages_read(self, event):
        await self.send(text_data=json.dumps(event))

    # =================================================================
    # 🔥 HÀM QUAN TRỌNG ĐÃ SỬA: Dùng URL từ Client để tránh lỗi Media
    # =================================================================
    @database_sync_to_async
    def save_message(self, conversation_id, text, attachment=None):
        try:            
            conversation = Conversation.objects.filter(
                id=conversation_id,
                participants=self.user
            ).first()
            
            if not conversation:
                return None

            message = Message(
                conversation=conversation,
                sender=self.user,
                text=text
            )

            # Biến để lưu URL chuẩn trả về cho Frontend
            final_url = None
            final_type = 'file'

            # 1. Xử lý attachment
            if attachment and isinstance(attachment, dict):
                # ✅ LẤY URL GỐC TỪ CLIENT (QUAN TRỌNG)
                # URL này là https://res.cloudinary.com/... đã đúng, không bị dính /media/
                final_url = attachment.get('url')
                final_type = attachment.get('type', 'file')
                
                if final_url:
                    # Chỉ lưu tên file vào DB để quản lý
                    filename = final_url.split('/')[-1]
                    message.attachment.name = f"chat_attachments/{filename}"

            # 2. Lưu vào DB     
            message.save()
            conversation.save()

            # 3. Chuẩn bị dữ liệu trả về
            # 🔥 NẾU CÓ URL TỪ CLIENT, DÙNG NÓ LUÔN (KHÔNG LẤY TỪ DB RA NỮA)
            # Điều này tránh việc Django tự động thêm '/media/' vào URL
            att_data = None
            if final_url:
                # Fix HTTPS và Auto
                if final_url.startswith("http:"):
                    final_url = final_url.replace("http:", "https:")
                
                if "/auto/upload/" in final_url:
                     if final_type == 'video':
                        final_url = final_url.replace("/auto/upload/", "/video/upload/")
                     else:
                        final_url = final_url.replace("/auto/upload/", "/image/upload/")

                att_data = {
                    'url': final_url,
                    'type': final_type
                }
            elif message.attachment:
                # Fallback: Nếu client không gửi URL (hiếm), mới lấy từ DB
                try:
                    att_data = {'url': message.attachment.url, 'type': 'file'}
                except: pass

            # Avatar
            avatar_url = None
            if self.user.avatar and hasattr(self.user.avatar, "url"):
                avatar_url = self.user.avatar.url
                if avatar_url.startswith("http:"): 
                    avatar_url = avatar_url.replace("http:", "https:")

            return {
                'id': message.id,
                'conversation': message.conversation.id,
                'sender': {
                    'id': self.user.id,
                    'username': self.user.username,
                    'name': f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username,
                    'avatar': avatar_url,
                },
                'text': message.text,
                'created_at': message.created_at.isoformat(),
                'is_read': message.is_read,
                'attachment': att_data # ✅ URL chuẩn sạch sẽ
            }
            
        except Exception as e:
            print(f"❌ [save_message] Error: {e}")
            traceback.print_exc()
            return None

    @database_sync_to_async
    def get_other_user_id(self, conversation_id):
        try:
            conversation = Conversation.objects.filter(id=conversation_id, participants=self.user).first()
            if conversation:
                for p in conversation.participants.all():
                    if p.id != self.user.id: return p.id
            return None
        except: return None
    
    @database_sync_to_async
    def mark_messages_as_read(self, conversation_id):
        try:
            Message.objects.filter(conversation_id=conversation_id, is_read=False).exclude(sender=self.user).update(is_read=True)
        except: pass
    
    @database_sync_to_async
    def set_user_online(self, is_online):
        try:
            status, _ = UserStatus.objects.get_or_create(user=self.user)
            status.is_online = is_online
            status.save()
        except: pass