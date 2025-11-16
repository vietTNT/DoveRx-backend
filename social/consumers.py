import json
import asyncio  # ✅ THÊM DÒNG NÀY
import traceback
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Post, Comment, PostReaction, CommentReaction
from .serializers import PostSerializer, CommentSerializer

class FeedConsumer(AsyncWebsocketConsumer):
    """
    Consumer xử lý feed real-time: posts, comments, reactions
    
    Events:
    - new_post: Bài viết mới
    - new_comment: Bình luận mới
    - delete_comment: Xóa bình luận (chỉ người tạo mới được xóa)
    - post_react: Thả cảm xúc trên post
    - comment_react: Thả cảm xúc trên comment
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

        # Join public feed group
        await self.channel_layer.group_add(
            self.feed_group_name,
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
            
        await self.channel_layer.group_discard(
            self.feed_group_name,
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
            
            print(f"📩 FeedConsumer received from {self.user.username}: {data}")

            # ✅ Pong response
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
            
            # ✅ Xóa bình luận
            elif message_type == 'delete_comment':
                await self.handle_delete_comment(data)
            
            # ✅ Typing indicator
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
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            print(f"❌ Error in receive: {e}")
            print(traceback.format_exc())
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    # ==================== HANDLERS ====================

    async def handle_delete_comment(self, data):
        """
        Xóa bình luận (chỉ người tạo mới được xóa)
        
        Client gửi:
        {
            "type": "delete_comment",
            "comment_id": 123
        }
        
        Broadcast đến tất cả:
        {
            "type": "feed_update",
            "data": {
                "event": "delete_comment",
                "post_id": 45,
                "comment_id": 123
            }
        }
        """
        try:
            comment_id = data.get('comment_id')
            
            if not comment_id:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Missing comment_id'
                }))
                return
            
            print(f"🗑️ [handle_delete_comment] User {self.user.username} deleting comment {comment_id}")
            
            # ✅ Xóa comment trong database (kiểm tra quyền)
            post_id = await self.delete_comment_sync(comment_id, self.user)
            
            if post_id:
                print(f"✅ [handle_delete_comment] Deleted comment {comment_id} from post {post_id}")
                
                # ✅ Broadcast to public feed
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
            else:
                print(f"❌ [handle_delete_comment] Failed to delete comment {comment_id}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Không thể xóa bình luận (không tồn tại hoặc không có quyền)'
                }))
                
        except Exception as e:
            print(f"❌ [handle_delete_comment] Error: {e}")
            print(traceback.format_exc())

    @sync_to_async
    def delete_comment_sync(self, comment_id, user):
        """Xóa comment trong database (chỉ người tạo mới được xóa)"""
        try:
            comment = Comment.objects.get(id=comment_id, user=user)
            post_id = comment.post.id
            comment.delete()
            print(f"✅ [delete_comment_sync] Comment {comment_id} deleted from DB")
            return post_id
        except Comment.DoesNotExist:
            print(f"❌ [delete_comment_sync] Comment {comment_id} not found")
            return None
        except Exception as e:
            print(f"❌ [delete_comment_sync] Error: {e}")
            print(traceback.format_exc())
            return None
    async def handle_post_react(self, data):
        post_id = data.get("post_id")
        reaction_type = data.get("reaction_type")

        if not post_id:
            return await self.send(text_data=json.dumps({"type": "error", "message": "Missing post_id"}))

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

    # ==================== EVENT HANDLERS ====================

    async def feed_update(self, event):
        """Broadcast feed update tới client"""
        try:
            await self.send(text_data=json.dumps({
                'type': 'feed_update',
                'data': event['data']
            }))
        except Exception as e:
            print(f"❌ Error sending feed_update: {e}")

    async def user_typing(self, event):
        """Broadcast typing status"""
        try:
            # Không gửi lại cho chính người đang typing
            if event['user_id'] != self.user.id:
                await self.send(text_data=json.dumps({
                    'type': 'user_typing',
                    'post_id': event['post_id'],
                    'user_id': event['user_id'],
                    'user_name': event['user_name'],
                    'is_typing': event['is_typing']
                }))
        except Exception as e:
            print(f"❌ Error sending typing: {e}")

    # ==================== HELPER METHODS ====================

    @sync_to_async
    def get_post_reactions(self, post_id):
        """Lấy số lượng reactions của post"""
        try:
            reactions = PostReaction.objects.filter(post_id=post_id).values('type')
            reaction_counts = {}
            for r in reactions:
                reaction_type = r['type']
                reaction_counts[reaction_type] = reaction_counts.get(reaction_type, 0) + 1
            return reaction_counts
        except Exception as e:
            print(f"❌ [get_post_reactions] Error: {e}")
            return {}

    @sync_to_async
    def get_comment_reactions(self, comment_id):
        """Lấy số lượng reactions của comment"""
        try:
            reactions = CommentReaction.objects.filter(comment_id=comment_id).values('type')
            reaction_counts = {}
            for r in reactions:
                reaction_type = r['type']
                reaction_counts[reaction_type] = reaction_counts.get(reaction_type, 0) + 1
            return reaction_counts
        except Exception as e:
            print(f"❌ [get_comment_reactions] Error: {e}")
            return {}
    # lưu vào DB
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
