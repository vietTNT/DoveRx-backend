import json
import asyncio
import traceback
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Post, Comment, PostReaction, CommentReaction

class FeedConsumer(AsyncWebsocketConsumer):
    """
    Consumer xử lý feed real-time: posts, comments, reactions, notifications
    """
    
    async def connect(self):
        """Kết nối WebSocket"""
        self.feed_group_name = 'public_feed'
        self.user = self.scope.get('user', AnonymousUser())
        self.ping_task = None

        if isinstance(self.user, AnonymousUser) or not self.user:
            print("❌ FeedConsumer: Anonymous user, closing connection")
            await self.close(code=4001)
            return

        # 1. Join Public Feed Group (Nhận tin chung: bài mới, like nhảy số...)
        await self.channel_layer.group_add(
            self.feed_group_name,
            self.channel_name
        )

        # 2. JOIN USER GROUP (QUAN TRỌNG: Để nhận thông báo cá nhân)
       
        self.user_group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Send welcome message
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Connected to feed as {self.user.username}',
            'user_id': self.user.id
        }))
        
        # Start keepalive
        self.ping_task = asyncio.create_task(self.send_periodic_ping())
        print(f"✅ FeedConsumer connected: {self.user.username}")

    async def disconnect(self, close_code):
        """Ngắt kết nối"""
        if self.ping_task:
            self.ping_task.cancel()
            
        # Rời nhóm Public
        await self.channel_layer.group_discard(
            self.feed_group_name,
            self.channel_name
        )
        
        # Rời nhóm User (nếu có)
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name, 
                self.channel_name
            )
            
        print(f"🔌 FeedConsumer disconnected: {self.user.username if self.user else 'Unknown'} (code: {close_code})")

    async def send_periodic_ping(self):
        """Gửi ping mỗi 30s để giữ connection"""
        try:
            while True:
                await asyncio.sleep(30)
                await self.send(text_data=json.dumps({
                    'type': 'ping',
                    'timestamp': str(asyncio.get_event_loop().time())
                }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ Ping error: {e}")

    async def receive(self, text_data):
        """Nhận tin nhắn từ client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            # print(f"📩 FeedConsumer received from {self.user.username}: {data}")

            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
            
            elif message_type == 'delete_comment':
                await self.handle_delete_comment(data)
            
            elif message_type == 'typing':
                await self.channel_layer.group_send(
                    self.feed_group_name,
                    {
                        'type': 'user_typing',
                        'post_id': data.get('post_id'),
                        'user_id': self.user.id,
                        'user_name': self.user.get_full_name() or self.user.username,
                        'is_typing': data.get('is_typing', True)
                    }
                )
                
            elif message_type == "post_react":
                await self.handle_post_react(data)

            else:
                # Ignore unknown types to prevent spamming client with errors
                pass 
                
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"❌ Error in receive: {e}")
            print(traceback.format_exc())
    async def send_notification(self, event):
        """
        Handler cho các thông báo chung (kết bạn, like, comment...)
        """
        data = event.get('data', {})
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': data
        }))
    # ==================== HANDLERS TỪ VIEWS GỬI SANG ====================

    async def feed_update(self, event):
        """Broadcast feed update (Public) tới client"""
        try:
            await self.send(text_data=json.dumps({
                'type': 'feed_update',
                'data': event['data']
            }))
        except Exception as e:
            print(f"❌ Error sending feed_update: {e}")

    async def feed_notification(self, event):
      
        try:
            # Views.py gửi type='feed_notification', ta forward xuống client
            data = event.get('data', {})
            await self.send(text_data=json.dumps({
                'type': 'notification',
                'data': data
            }))
        except Exception as e:
            print(f"❌ Error sending notification: {e}")

    async def user_typing(self, event):
        """Broadcast typing status"""
        try:
            if event['user_id'] != self.user.id:
                await self.send(text_data=json.dumps(event))
        except Exception as e:
            print(f"❌ Error sending typing: {e}")

    # ==================== LOGIC XỬ LÝ (CLIENT GỬI LÊN) ====================

    async def handle_delete_comment(self, data):
        try:
            comment_id = data.get('comment_id')
            if not comment_id: return
            
            print(f"🗑️ User {self.user.username} deleting comment {comment_id}")
            
            post_id = await self.delete_comment_sync(comment_id, self.user)
            
            if post_id:
                await self.channel_layer.group_send(
                    'public_feed',
                    {
                        'type': 'feed_update',
                        'data': {
                            'event': 'delete_comment',
                            'post_id': post_id,
                            'comment_id': comment_id,
                        }
                    }
                )
        except Exception as e:
            print(f"❌ [handle_delete_comment] Error: {e}")

    async def handle_post_react(self, data):
        post_id = data.get("post_id")
        reaction_type = data.get("reaction_type")

        if not post_id: return

        # Lưu DB
        await self.toggle_post_reaction_sync(post_id, self.user, reaction_type)

        # Get lại số lượng
        reaction_counts = await self.get_post_reactions(post_id)

        # Broadcast realtime
        await self.channel_layer.group_send(
            "public_feed",
            {
                "type": "feed_update",
                "data": {
                    "event": "post_react",
                    "post_id": post_id,
                    "reaction_type": reaction_type,
                    "reaction_counts": reaction_counts,
                    "user_id": self.user.id
                }
            }
        )
    async def chat_new_message(self, event):
    # Pass là an toàn nhất, chỉ đơn giản là bỏ qua thông điệp này
        pass 

# Hàm này sẽ được gọi khi FeedConsumer nhận type: 'chat.user_typing'
    async def chat_user_typing(self, event):
    # Thông điệp chat typing, FeedConsumer không cần xử lý
        pass

# Hàm này sẽ được gọi khi FeedConsumer nhận type: 'chat.messages_read'
    async def chat_messages_read(self, event):
    # Thông điệp đã đọc, FeedConsumer không cần xử lý
        pass
    # ==================== DATABASE SYNC METHODS ====================

    @sync_to_async
    def delete_comment_sync(self, comment_id, user):
        try:
            comment = Comment.objects.get(id=comment_id, author=user)
            post_id = comment.post.id
            comment.delete()
            return post_id
        except:
            return None

    @sync_to_async
    def toggle_post_reaction_sync(self, post_id, user, reaction_type):
        if reaction_type is None:
            PostReaction.objects.filter(post_id=post_id, user=user).delete()
            return
        PostReaction.objects.update_or_create(
            post_id=post_id,
            user=user,
            defaults={"type": reaction_type}
        )

    @sync_to_async
    def get_post_reactions(self, post_id):
        try:
            reactions = PostReaction.objects.filter(post_id=post_id).values('type')
            reaction_counts = {}
            for r in reactions:
                reaction_type = r['type']
                reaction_counts[reaction_type] = reaction_counts.get(reaction_type, 0) + 1
            return reaction_counts
        except:
            return {}
    # Hàm này sẽ được gọi khi FeedConsumer nhận type: 'chat.new_message'
