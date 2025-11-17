# from rest_framework import viewsets, permissions, status
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from django.db import transaction
# from .models import Post, PostMedia, PostReaction, Comment, CommentReaction, Share
# from .serializers import PostSerializer, CommentSerializer

# class PostViewSet(viewsets.ModelViewSet):
#     queryset = (
#         Post.objects
#         .select_related("author")
#         .prefetch_related("media", "reactions", "comments")
#         .order_by("-created_at")  # 🟢 thêm dòng này
#     )
#     serializer_class = PostSerializer

#     def get_permissions(self):
#         return [permissions.AllowAny()] if self.action in ["list","retrieve"] else [permissions.IsAuthenticated()]

#     def perform_create(self, serializer):
#         serializer.save(author=self.request.user)

#     @transaction.atomic
#     def create(self, request, *args, **kwargs):
#         kind = request.data.get("kind", "normal")
#         content_text = request.data.get("content") or ""
#         content_medical = request.data.get("content_medical")
#         p = Post.objects.create(
#             author=request.user,
#             kind=kind,
#             content_text=content_text if kind=="normal" else None,
#             content_medical=content_medical if kind=="medical" else None,
#             visibility=request.data.get("visibility","public"),
#         )
#         for f in request.FILES.getlist("media"):
#             mt = "video" if (getattr(f,"content_type","").startswith("video")) else "image"
#             PostMedia.objects.create(post=p, file=f, media_type=mt)
#         return Response(PostSerializer(p, context={"request": request}).data, status=201)

#     @action(detail=True, methods=["post", "delete"], url_path="reactions")
#     def reactions(self, request, pk=None):
#         post = self.get_object()
#         if request.method == "DELETE":
#             PostReaction.objects.filter(post=post, user=request.user).delete()
#             return Response({"ok": True})
#         rtype = request.data.get("type")
#         if not rtype: return Response({"error": "Missing type"}, status=400)
#         PostReaction.objects.update_or_create(post=post, user=request.user, defaults={"type": rtype})
#         return Response({"ok": True, "type": rtype})

#     @action(detail=True, methods=["post"], url_path="share")
#     def share(self, request, pk=None):
#         post = self.get_object()
#         Share.objects.create(post=post, user=request.user, message=request.data.get("message",""))
#         return Response({"ok": True, "shares": post.shares.count()})

# class CommentViewSet(viewsets.GenericViewSet):
#     queryset = Comment.objects.select_related("author","post").prefetch_related("replies","reactions")
#     permission_classes = [permissions.IsAuthenticated]
#     serializer_class = CommentSerializer

#     def list(self, request):
#         post_id = request.query_params.get("post")
#         if not post_id: return Response({"error":"Missing post"}, status=400)
#         roots = Comment.objects.filter(post_id=post_id, parent__isnull=True).order_by("created_at")
#         return Response(CommentSerializer(roots, many=True, context={"request": request}).data)

#     def create(self, request):
#         post_id = request.data.get("post")
#         text = (request.data.get("text") or "").strip()
#         parent_id = request.data.get("parent")
#         if not post_id or not text: return Response({"error":"Missing post/text"}, status=400)
#         c = Comment.objects.create(post_id=post_id, author=request.user, text=text, parent_id=parent_id or None)
#         return Response(CommentSerializer(c, context={"request": request}).data, status=201)

#     def partial_update(self, request, pk=None):
#         c = self.get_queryset().get(pk=pk, author=request.user)
#         c.text = (request.data.get("text") or c.text).strip()
#         c.save()
#         return Response(CommentSerializer(c, context={"request": request}).data)

#     def destroy(self, request, pk=None):
#         c = self.get_queryset().get(pk=pk, author=request.user)
#         c.delete()
#         return Response(status=204)

#     @action(detail=True, methods=["post","delete"], url_path="reactions")
#     def reactions(self, request, pk=None):
#         c = self.get_queryset().get(pk=pk)
#         if request.method == "DELETE":
#             CommentReaction.objects.filter(comment=c, user=request.user).delete()
#             return Response({"ok": True})
#         rtype = request.data.get("type")
#         if not rtype: return Response({"error":"Missing type"}, status=400)
#         CommentReaction.objects.update_or_create(comment=c, user=request.user, defaults={"type": rtype})
#         return Response({"ok": True, "type": rtype})


from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
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
        return [permissions.AllowAny()] if self.action in ["list","retrieve"] else [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        kind = request.data.get("kind", "normal")
        content_text = request.data.get("content") or ""
        content_medical = request.data.get("content_medical")
        p = Post.objects.create(
            author=request.user,
            kind=kind,
            content_text=content_text if kind=="normal" else None,
            content_medical=content_medical if kind=="medical" else None,
            visibility=request.data.get("visibility","public"),
        )
        for f in request.FILES.getlist("media"):
            # mt = "video" if (getattr(f,"content_type","").startswith("video")) else "image"
            mt = "video" if f.content_type.startswith("video") else "image"
            PostMedia.objects.create(post=p, file=f, media_type=mt)
        
        # Serialize post
        post_data = PostSerializer(p, context={"request": request}).data
        
        # 🔥 Broadcast new_post qua WebSocket
        self._broadcast('new_post', {'post': post_data})
        
        return Response(post_data, status=201)

    def update(self, request, *args, **kwargs):
        """Override update để broadcast"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Kiểm tra quyền
        if instance.author != request.user:
            return Response({'error': 'You can only edit your own posts'}, status=403)
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # 🔥 Broadcast update_post
        self._broadcast('update_post', {'post': serializer.data})
        
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Override destroy để broadcast"""
        instance = self.get_object()
        
        if instance.author != request.user:
            return Response({'error': 'You can only delete your own posts'}, status=403)
        
        post_id = instance.id
        instance.delete()
        
        # 🔥 Broadcast delete_post
        self._broadcast('delete_post', {'post_id': post_id})
        
        return Response(status=204)

    @action(detail=True, methods=["post", "delete"], url_path="reactions")
    def reactions(self, request, pk=None):
        post = self.get_object()
        
        if request.method == "DELETE":
            deleted = PostReaction.objects.filter(post=post, user=request.user).delete()
            if deleted[0] > 0:
                # 🔥 Broadcast unreact
                self._broadcast('post_unreact', {
                    'post_id': post.id,
                    'user_id': request.user.id,
                    'reaction_counts': self._get_reaction_counts(post)
                })
            return Response({"ok": True})
        
        rtype = request.data.get("type")
        if not rtype: 
            return Response({"error": "Missing type"}, status=400)
        
        # Update or create reaction
        reaction, created = PostReaction.objects.update_or_create(
            post=post, user=request.user, defaults={"type": rtype}
        )
        
        # 🔥 Broadcast react/change_react
        event = 'post_react' if created else 'post_change_react'
        self._broadcast(event, {
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
        message = request.data.get("message","")
        
        Share.objects.create(post=post, user=request.user, message=message)
        shares_count = post.shares.count()
        
        # 🔥 Broadcast share_post
        self._broadcast('share_post', {
            'post_id': post.id,
            'user_id': request.user.id,
            'user_name': request.user.get_full_name() or request.user.username,
            'message': message,
            'shares_count': shares_count
        })
        
        return Response({"ok": True, "shares": shares_count})

    def _broadcast(self, event_type, data):
        """Helper method để broadcast qua WebSocket"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'public_feed',
            {
                'type': 'feed_update',
                'data': {
                    'event': event_type,
                    **data
                }
            }
        )

    def _get_reaction_counts(self, post):
        """Helper để đếm reactions"""
        from django.db.models import Count
        agg = post.reactions.values("type").annotate(count=Count("id"))
        return {x["type"]: x["count"] for x in agg}


class CommentViewSet(viewsets.GenericViewSet):
    queryset = Comment.objects.select_related("author","post").prefetch_related("replies","reactions")
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommentSerializer

    def list(self, request):
        post_id = request.query_params.get("post")
        if not post_id: 
            return Response({"error":"Missing post"}, status=400)
        roots = Comment.objects.filter(post_id=post_id, parent__isnull=True).order_by("created_at")
        return Response(CommentSerializer(roots, many=True, context={"request": request}).data)

    def create(self, request):
        post_id = request.data.get("post")
        text = (request.data.get("text") or "").strip()
        parent_id = request.data.get("parent")
        
        if not post_id or not text: 
            return Response({"error":"Missing post/text"}, status=400)
        
        c = Comment.objects.create(
            post_id=post_id, 
            author=request.user, 
            text=text, 
            parent_id=parent_id or None
        )
        
        comment_data = CommentSerializer(c, context={"request": request}).data
        
        # 🔥 Broadcast new_comment
        self._broadcast('new_comment', {
            'post_id': int(post_id),
            'comment': comment_data,
            'is_reply': parent_id is not None
        })
        
        return Response(comment_data, status=201)

    def partial_update(self, request, pk=None):
        c = self.get_queryset().get(pk=pk, author=request.user)
        c.text = (request.data.get("text") or c.text).strip()
        c.save()
        
        comment_data = CommentSerializer(c, context={"request": request}).data
        
        # 🔥 Broadcast update_comment
        self._broadcast('update_comment', {
            'post_id': c.post.id,
            'comment': comment_data
        })
        
        return Response(comment_data)

    def destroy(self, request, pk=None):
        c = self.get_queryset().get(pk=pk, author=request.user)
        post_id = c.post.id
        comment_id = c.id
        c.delete()
        
        # 🔥 Broadcast delete_comment
        self._broadcast('delete_comment', {
            'post_id': post_id,
            'comment_id': comment_id
        })
        
        return Response(status=204)

    @action(detail=True, methods=["post","delete"], url_path="reactions")
    def reactions(self, request, pk=None):
        c = self.get_queryset().get(pk=pk)
        
        if request.method == "DELETE":
            deleted = CommentReaction.objects.filter(comment=c, user=request.user).delete()
            if deleted[0] > 0:
                # 🔥 Broadcast comment_unreact
                self._broadcast('comment_unreact', {
                    'post_id': c.post.id,
                    'comment_id': c.id,
                    'user_id': request.user.id,
                    'reactions_count': c.reactions.count()
                })
            return Response({"ok": True})
        
        rtype = request.data.get("type")
        if not rtype: 
            return Response({"error":"Missing type"}, status=400)
        
        reaction, created = CommentReaction.objects.update_or_create(
            comment=c, user=request.user, defaults={"type": rtype}
        )
        
        # 🔥 Broadcast comment_react
        event = 'comment_react' if created else 'comment_change_react'
        self._broadcast(event, {
            'post_id': c.post.id,
            'comment_id': c.id,
            'user_id': request.user.id,
            'user_name': request.user.get_full_name() or request.user.username,
            'reaction_type': rtype,
            'reactions_count': c.reactions.count()
        })
        
        return Response({"ok": True, "type": rtype})

    def _broadcast(self, event_type, data):
        """Helper method để broadcast qua WebSocket"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'public_feed',
            {
                'type': 'feed_update',
                'data': {
                    'event': event_type,
                    **data
                }
            }
        )


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_comment(request, post_id):
    """Tạo bình luận mới"""
    try:
        post = Post.objects.get(id=post_id)
        parent_id = request.data.get('parent_id')
        
        comment = Comment.objects.create(
            post=post,
            user=request.user,
            text=request.data.get('text'),
            parent_id=parent_id
        )
        
        serializer = CommentSerializer(comment)
        
        # ✅ Broadcast qua WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'public_feed',
            {
                'type': 'feed_update',
                'data': {
                    'event': 'new_comment',
                    'post_id': post_id,
                    'comment': serializer.data
                }
            }
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Post.DoesNotExist:
        return Response({'error': 'Post not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_comment(request, comment_id):
    """Xóa bình luận - CHỈ NGƯỜI TẠO mới được xóa"""
    try:
        comment = Comment.objects.get(id=comment_id)
        
        # ✅ Kiểm tra quyền
        if comment.user.id != request.user.id:
            return Response(
                {'error': 'Bạn không có quyền xóa bình luận này'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        post_id = comment.post.id
        comment.delete()
        
        # ✅ Broadcast qua WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'public_feed',
            {
                'type': 'feed_update',
                'data': {
                    'event': 'delete_comment',
                    'post_id': post_id,
                    'comment_id': comment_id,
                    'deleted_by': request.user.id
                }
            }
        )
        
        return Response({'message': 'Đã xóa bình luận'}, status=status.HTTP_200_OK)
    except Comment.DoesNotExist:
        return Response({'error': 'Comment not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_post_reaction(request, post_id):
    """Thả cảm xúc trên post"""
    try:
        post = Post.objects.get(id=post_id)
        reaction_type = request.data.get('type', 'like')
        
        # Toggle reaction
        reaction, created = PostReaction.objects.get_or_create(
            post=post,
            user=request.user,
            defaults={'type': reaction_type}
        )
        
        if not created:
            if reaction.type == reaction_type:
                # Xóa reaction nếu đã có
                reaction.delete()
                action = 'removed'
            else:
                # Đổi loại reaction
                reaction.type = reaction_type
                reaction.save()
                action = 'updated'
        else:
            action = 'added'
        
        # ✅ Đếm lại số lượng reactions
        reactions = PostReaction.objects.filter(post=post).values('type')
        reaction_counts = {}
        for r in reactions:
            rt = r['type']
            reaction_counts[rt] = reaction_counts.get(rt, 0) + 1
        
        # ✅ Broadcast qua WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'public_feed',
            {
                'type': 'feed_update',
                'data': {
                    'event': 'post_react',
                    'post_id': post_id,
                    'reaction_counts': reaction_counts,
                    'user_id': request.user.id,
                    'reaction_type': None if action == 'removed' else reaction_type,
                    'action': action
                }
            }
        )
        
        return Response({
            'action': action,
            'reaction_counts': reaction_counts
        }, status=status.HTTP_200_OK)
        
    except Post.DoesNotExist:
        return Response({'error': 'Post not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_comment_reaction(request, comment_id):
    """Thả cảm xúc trên comment"""
    try:
        comment = Comment.objects.get(id=comment_id)
        reaction_type = request.data.get('type', 'like')
        
        # Toggle reaction
        reaction, created = CommentReaction.objects.get_or_create(
            comment=comment,
            user=request.user,
            defaults={'type': reaction_type}
        )
        
        if not created:
            if reaction.type == reaction_type:
                reaction.delete()
                action = 'removed'
            else:
                reaction.type = reaction_type
                reaction.save()
                action = 'updated'
        else:
            action = 'added'
        
        # ✅ Đếm lại reactions
        reactions = CommentReaction.objects.filter(comment=comment).values('type')
        reaction_counts = {}
        for r in reactions:
            rt = r['type']
            reaction_counts[rt] = reaction_counts.get(rt, 0) + 1
        
        # ✅ Broadcast qua WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'public_feed',
            {
                'type': 'feed_update',
                'data': {
                    'event': 'comment_react',
                    'comment_id': comment_id,
                    'post_id': comment.post.id,
                    'reaction_counts': reaction_counts,
                    'user_id': request.user.id,
                    'action': action
                }
            }
        )
        
        return Response({
            'action': action,
            'reaction_counts': reaction_counts
        }, status=status.HTTP_200_OK)
        
    except Comment.DoesNotExist:
        return Response({'error': 'Comment not found'}, status=status.HTTP_404_NOT_FOUND)