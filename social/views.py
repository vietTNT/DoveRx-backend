from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Count  # ✅ Move lên đầu file
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Post, PostMedia, PostReaction, Comment, CommentReaction, Share
from .serializers import PostSerializer, CommentSerializer

class PostViewSet(viewsets.ModelViewSet):
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

    # ✅ QUAN TRỌNG: Thêm method này để truyền request vào serializer
    # Giúp PostSerializer.get_user_reaction hoạt động đúng
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

        for f in request.FILES.getlist("media"):
            mt = "video" if f.content_type.startswith("video") else "image"
            PostMedia.objects.create(post=p, file=f, media_type=mt)
        
        # ✅ Lấy context chuẩn từ viewset
        serializer = self.get_serializer(p)
        post_data = serializer.data
        
        self._broadcast('new_post', {'post': post_data})
        return Response(post_data, status=201)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user:
            return Response({'error': 'Bạn chỉ có thể chỉnh sửa bài viết của mình'}, status=403)
        
        response = super().update(request, *args, **kwargs)
        self._broadcast('update_post', {'post': response.data})
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user:
            return Response({'error': 'Bạn chỉ có thể xóa bài viết của mình'}, status=403)
        
        post_id = instance.id
        instance.delete()
        self._broadcast('delete_post', {'post_id': post_id})
        return Response(status=204)

    @action(detail=True, methods=["post", "delete"], url_path="reactions")
    def reactions(self, request, pk=None):
        post = self.get_object()
        
        # 1. BỎ LIKE
        if request.method == "DELETE":
            deleted = PostReaction.objects.filter(post=post, user=request.user).delete()
            if deleted[0] > 0:
                self._broadcast('post_react', {
                    'post_id': post.id,
                    'user_id': request.user.id,
                    'reaction_type': None, 
                    'reaction_counts': self._get_reaction_counts(post)
                })
            return Response({"ok": True})
        
        # 2. THÊM/SỬA LIKE
        rtype = request.data.get("type")
        if not rtype: 
            return Response({"error": "Missing type"}, status=400)
        
        PostReaction.objects.update_or_create(
            post=post, user=request.user, defaults={"type": rtype}
        )
        
        self._broadcast('post_react', {
            'post_id': post.id,
            'user_id': request.user.id,
            'user_name': request.user.get_full_name() or request.user.username,
            'reaction_type': rtype,
            'reaction_counts': self._get_reaction_counts(post)
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

    def _broadcast(self, event_type, data):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'public_feed',
            {'type': 'feed_update', 'data': {'event': event_type, **data}}
        )

    def _get_reaction_counts(self, post):
        agg = post.reactions.values("type").annotate(count=Count("id"))
        return {x["type"]: x["count"] for x in agg}


class CommentViewSet(viewsets.GenericViewSet):
    queryset = Comment.objects.select_related("author", "post").prefetch_related("replies", "reactions")
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommentSerializer

    # ✅ Thêm context để serializer lấy được request user (quan trọng cho comment reaction)
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
        
        c = Comment.objects.create(
            post_id=post_id, 
            author=request.user, 
            text=text, 
            parent_id=parent_id or None
        )
        
        # ✅ Lấy data từ serializer (có context)
        comment_data = self.get_serializer(c).data
        
        self._broadcast('new_comment', {
            'post_id': int(post_id),
            'comment': comment_data,
            'is_reply': parent_id is not None
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
                    'reactions_count': self._get_reaction_counts(c)
                })
            return Response({"ok": True})
        
        rtype = request.data.get("type")
        if not rtype: return Response({"error": "Missing type"}, status=400)
        
        CommentReaction.objects.update_or_create(
            comment=c, user=request.user, defaults={"type": rtype}
        )
        
        self._broadcast('comment_react', {
            'post_id': c.post.id,
            'comment_id': c.id,
            'user_id': request.user.id,
            'user_name': request.user.get_full_name() or request.user.username,
            'reaction_type': rtype,
            'reactions_count': self._get_reaction_counts(c)
        })
        return Response({"ok": True, "type": rtype})

    def _broadcast(self, event_type, data):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'public_feed',
            {'type': 'feed_update', 'data': {'event': event_type, **data}}
        )
        
    def _get_reaction_counts(self, comment):
        agg = comment.reactions.values("type").annotate(count=Count("id"))
        return {x["type"]: x["count"] for x in agg}