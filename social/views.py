from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Count 
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Post, PostMedia, PostReaction, Comment, CommentReaction, Share, Notification
from .serializers import PostSerializer, CommentSerializer, UserBasicSerializer, NotificationSerializer
from django.db.models import Q
from accounts.models import Friendship  
# =================================================================
# 1. BASE CLASS (MIXIN) - Chứa logic chung để tái sử dụng
# =================================================================
class BaseBroadcastViewSet(viewsets.GenericViewSet):
    """
    Class cha chứa các hàm helper dùng chung cho Post và Comment.
    Giúp code gọn gàng, tránh lặp lại.
    """

    def _get_avatar_url(self, user):
        try:
            if user.avatar:
                return user.avatar.url
        except:
            pass
        return None

    def _broadcast(self, event_type, data):
        """Gửi tin nhắn tới kênh chung (Public Feed) để cập nhật UI cho mọi người"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'public_feed',
            {'type': 'feed_update', 'data': {'event': event_type, **data}}
        )

    def create_notification(self, recipient, sender, type, text, post=None, comment=None, extra_data=None):
        """
      
        1. Lưu thông báo vào Database.
        2. Gửi WebSocket riêng cho người nhận (để hiện popup/âm thanh).
        """
        # Không thông báo nếu tự like/cmt bài mình
        if recipient.id == sender.id:
            return

        # A. Lưu vào DB
        notif = Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type=type,
            text=text,
            post=post,
            comment=comment
        )

        # B. Chuẩn bị dữ liệu Socket (Format khớp với Frontend)
        socket_payload = {
            'id': notif.id,
            'type': type, # post_react, new_comment...
            'text': text,
            'created_at': notif.created_at.isoformat(),
            'sender': {
                'id': sender.id,
                'name': sender.get_full_name() or sender.username,
                'avatar': self._get_avatar_url(sender)
            },
            'post_id': post.id if post else None,
            'comment_id': comment.id if comment else None,
            'is_read': False,
            
            # Dữ liệu bổ sung (để tương thích logic cũ của Navbar nếu cần)
            'owner_id': recipient.id, 
            'user_id': sender.id,
            'user_name': sender.get_full_name() or sender.username,
            'user_avatar': self._get_avatar_url(sender),
        }
        
        if extra_data:
            socket_payload.update(extra_data)

        # C. Gửi WebSocket tới GROUP RIÊNG của user (user_{id})
        # Lưu ý: Cần đảm bảo consumers.py đã join user vào group này
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{recipient.id}', 
            {'type': 'feed_notification', 'data': socket_payload} 
        )

# =================================================================
# 2. NOTIFICATION VIEWSET - API lấy danh sách thông báo
# =================================================================
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'status': 'ok'})
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save()
        return Response({'status': 'ok'})

# =================================================================
# 3. POST VIEWSET - Kế thừa từ BaseBroadcastViewSet
# =================================================================
class PostViewSet(BaseBroadcastViewSet, viewsets.ModelViewSet):
    queryset = (
        Post.objects
        .select_related("author")
        .prefetch_related("media", "reactions", "comments")
        .order_by("-created_at")
    )
    serializer_class = PostSerializer

    def get_permissions(self):
        return [permissions.AllowAny()] if self.action in ["list", "retrieve"] else [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        kind = request.data.get("kind", "normal")
        content_text = request.data.get("content") or ""
        content_medical = request.data.get("content_medical")
        
        p = Post.objects.create(
            author=request.user,
            kind=kind,
            content_text=content_text if kind == "normal" else None,
            content_medical=content_medical if kind == "medical" else None,
            visibility=request.data.get("visibility", "public"),
        )

        if request.FILES.getlist("media"):
            for f in request.FILES.getlist("media"):
                mt = "video" if f.content_type.startswith("video") else "image"
                PostMedia.objects.create(post=p, file=f, media_type=mt)
        
        serializer = self.get_serializer(p)
        post_data = serializer.data
        
        # Broadcast bài viết mới ra public feed (chưa cần lưu notif ở đây trừ khi muốn báo cho bạn bè)
        self._broadcast('new_post', {
            'post': post_data,
            'user_id': request.user.id,
            'user_name': request.user.get_full_name() or request.user.username
        })
        try:
            friendships = Friendship.objects.filter(
                (Q(from_user=request.user) | Q(to_user=request.user)) & 
                Q(status='accepted')
            )
            
            for f in friendships:
                # ✅ FIX LỖI: Xác định friend là ai
                friend = f.to_user if f.from_user == request.user else f.from_user
                
                self.create_notification(
                    recipient=friend, 
                    sender=request.user, 
                    type='new_post', 
                    text=f"{request.user.username} đã đăng bài viết mới.", 
                    post=p
                )
        except Exception as e:
            print(f"❌ Error notifying friends: {e}")

        return Response(post_data, status=201)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user:
            return Response({'error': 'Bạn chỉ có thể chỉnh sửa bài viết của mình'}, status=403)
        
        new_content = request.data.get("content")
        if new_content is not None and instance.kind == "normal":
            instance.content_text = new_content
            instance.save()
        
        kwargs['partial'] = True
        super().update(request, *args, **kwargs)
        
        instance.refresh_from_db()
        serializer = self.get_serializer(instance)
        self._broadcast('update_post', {'post': serializer.data})
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user:
            return Response({'error': 'Bạn chỉ có thể xóa bài viết của mình'}, status=403)
        
        post_id = instance.id
        instance.delete()
        self._broadcast('delete_post', {'post_id': post_id})
        return Response(status=204)

    @action(detail=True, methods=["get", "post", "delete"], url_path="reactions")
    def reactions(self, request, pk=None):
        post = self.get_object()
        
        if request.method == "GET":
            reactions = PostReaction.objects.filter(post=post).select_related('user')
            data = []
            for r in reactions:
                data.append({
                    "user": UserBasicSerializer(r.user, context={"request": request}).data,
                    "type": r.type
                })
            return Response(data)

        # 1. BỎ LIKE
        if request.method == "DELETE":
            deleted = PostReaction.objects.filter(post=post, user=request.user).delete()
            if deleted[0] > 0:
                self._broadcast('post_react', {
                    'post_id': post.id,
                    'user_id': request.user.id,
                    'reaction_type': None, 
                    'reaction_counts': self._get_reaction_counts(post),
                    'owner_id': post.author.id
                })
            return Response({"ok": True})
        
        # 2. THÊM/SỬA LIKE
        rtype = request.data.get("type")
        if not rtype: return Response({"error": "Missing type"}, status=400)
        
        PostReaction.objects.update_or_create(
            post=post, user=request.user, defaults={"type": rtype}
        )
        
        #  A. Lưu DB & Gửi thông báo cá nhân cho chủ bài viết
        self.create_notification(
            recipient=post.author,
            sender=request.user,
            type='post_react',
            text=f"{request.user.username} đã bày tỏ cảm xúc về bài viết của bạn.",
            post=post,
            extra_data={'reaction_type': rtype}
        )

        #  B. Broadcast ra Public Feed để mọi người thấy số like nhảy
        self._broadcast('post_react', {
            'post_id': post.id,
            'user_id': request.user.id,
            'user_name': request.user.get_full_name() or request.user.username,
            'user_avatar': self._get_avatar_url(request.user),
            'reaction_type': rtype,
            'reaction_counts': self._get_reaction_counts(post),
            'owner_id': post.author.id,
        })
        return Response({"ok": True, "type": rtype})

    @action(detail=True, methods=["post"], url_path="share")
    def share(self, request, pk=None):
        post = self.get_object()
        message = request.data.get("message", "")
        Share.objects.create(post=post, user=request.user, message=message)
        shares_count = post.shares.count()
        
        self._broadcast('share_post', {
            'post_id': post.id,
            'user_id': request.user.id,
            'message': message,
            'shares_count': shares_count
        })
        return Response({"ok": True, "shares": shares_count})

    def _get_reaction_counts(self, post):
        agg = post.reactions.values("type").annotate(count=Count("id"))
        return {x["type"]: x["count"] for x in agg}


# =================================================================
# 4. COMMENT VIEWSET - Kế thừa từ BaseBroadcastViewSet
# =================================================================
class CommentViewSet(BaseBroadcastViewSet):
    queryset = Comment.objects.select_related("author", "post").prefetch_related("replies", "reactions")
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommentSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def list(self, request):
        post_id = request.query_params.get("post")
        if not post_id: return Response({"error": "Missing post"}, status=400)
        roots = Comment.objects.filter(post_id=post_id, parent__isnull=True).order_by("created_at")
        return Response(CommentSerializer(roots, many=True, context={"request": request}).data)

    def create(self, request):
        post_id = request.data.get("post")
        text = (request.data.get("text") or "").strip()
        parent_id = request.data.get("parent")
        
        if not post_id or not text: 
            return Response({"error": "Missing post/text"}, status=400)
        
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=404)

        c = Comment.objects.create(
            post=post, 
            author=request.user, 
            text=text, 
            parent_id=parent_id or None
        )
        
        comment_data = self.get_serializer(c).data
        
        # Lưu DB & Gửi thông báo
        # Nếu là reply -> Báo cho chủ comment cha
        # Nếu là comment gốc -> Báo cho chủ bài viết
        recipient = c.parent.author if c.parent else c.post.author
        action_text = "đã trả lời bình luận của bạn" if c.parent else "đã bình luận về bài viết của bạn"
        
        self.create_notification(
            recipient=recipient,
            sender=request.user,
            type='new_comment',
            text=f"{request.user.username} {action_text}: {text[:30]}...",
            post=post,
            comment=c
        )

        #  Broadcast ra Public Feed
        self._broadcast('new_comment', {
            'post_id': int(post_id),
            'comment': {
                **comment_data,
                'user_id': request.user.id, 
                'user_name': request.user.get_full_name() or request.user.username,
                'user_avatar': self._get_avatar_url(request.user) 
            },
            'is_reply': parent_id is not None,
            'post_author_id': c.post.author.id,
            'parent_author_id': c.parent.author.id if c.parent else None
        })
        return Response(comment_data, status=201)

    def partial_update(self, request, pk=None):
        c = self.get_queryset().get(pk=pk)
        if c.author != request.user:
            return Response({'error': 'Bạn không có quyền sửa bình luận này'}, status=403)

        c.text = (request.data.get("text") or c.text).strip()
        c.save()
        
        comment_data = self.get_serializer(c).data
        self._broadcast('update_comment', {'post_id': c.post.id, 'comment': comment_data})
        return Response(comment_data)

    def destroy(self, request, pk=None):
        try:
            c = Comment.objects.get(pk=pk)
        except Comment.DoesNotExist:
            return Response(status=404)

        if c.author != request.user:
            return Response({'error': 'Bạn không có quyền xóa bình luận này'}, status=403)

        post_id = c.post.id
        comment_id = c.id
        c.delete()
        
        self._broadcast('delete_comment', {
            'post_id': post_id, 
            'comment_id': comment_id,
            'deleted_by': request.user.id
        })
        return Response(status=204)

    @action(detail=True, methods=["post", "delete"], url_path="reactions")
    def reactions(self, request, pk=None):
        c = self.get_queryset().get(pk=pk)
        
        if request.method == "DELETE":
            deleted = CommentReaction.objects.filter(comment=c, user=request.user).delete()
            if deleted[0] > 0:
                self._broadcast('comment_react', {
                    'post_id': c.post.id,
                    'comment_id': c.id,
                    'user_id': request.user.id,
                    'reaction_type': None,
                    'reactions_count': self._get_reaction_counts(c),
                    'owner_id': c.author.id
                })
            return Response({"ok": True})
        
        rtype = request.data.get("type")
        if not rtype: return Response({"error": "Missing type"}, status=400)
        
        CommentReaction.objects.update_or_create(
            comment=c, user=request.user, defaults={"type": rtype}
        )
        
        #  Lưu DB & Gửi thông báo cá nhân cho chủ comment
        self.create_notification(
            recipient=c.author,
            sender=request.user,
            type='comment_react',
            text=f"{request.user.username} đã bày tỏ cảm xúc về bình luận của bạn.",
            post=c.post,
            comment=c,
            extra_data={'reaction_type': rtype}
        )

        #  B. Broadcast ra Public Feed
        self._broadcast('comment_react', {
            'post_id': c.post.id,
            'comment_id': c.id,
            'user_id': request.user.id,
            'user_name': request.user.get_full_name() or request.user.username,
            'user_avatar': self._get_avatar_url(request.user),               
            'reaction_type': rtype,
            'reactions_count': self._get_reaction_counts(c),
            'owner_id': c.author.id 
        })
        return Response({"ok": True, "type": rtype})
        
    def _get_reaction_counts(self, comment):
        agg = comment.reactions.values("type").annotate(count=Count("id"))
        return {x["type"]: x["count"] for x in agg}