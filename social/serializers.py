from rest_framework import serializers
from django.db import models
from django.contrib.auth import get_user_model
from .models import Post, PostMedia, PostReaction, Comment, CommentReaction, Share

User = get_user_model()

# ✅ THÊM: Helper function để map reaction icon/label
def get_reaction_display(reaction_type):
    """Trả về icon và label tương ứng với loại reaction"""
    reaction_map = {
        'like': {'icon': '👍', 'label': 'Thích'},
        'love': {'icon': '❤️', 'label': 'Yêu thích'},
        'care': {'icon': '🥰', 'label': 'Thương thương'},
        'haha': {'icon': '😂', 'label': 'Haha'},
        'wow': {'icon': '😮', 'label': 'Wow'},
        'sad': {'icon': '😢', 'label': 'Buồn'},
        'angry': {'icon': '😡', 'label': 'Phẫn nộ'},
    }
    return reaction_map.get(reaction_type, {'icon': '👍', 'label': 'Thích'})


class UserBasicSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ["id", "name", "avatar", "email"]
    
    def get_name(self, obj):
        return obj.get_full_name() or obj.username or obj.email
    
    def get_avatar(self, obj):
        try:
            url = obj.avatar.url
            req = self.context.get("request")
            return req.build_absolute_uri(url) if req else url
        except Exception:
            return None


class PostMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    
    class Meta:
        model = PostMedia
        fields = ["id", "url", "type"]
    
    # def get_url(self, obj):
    #     req = self.context.get("request")
    #     url = obj.file.url
    #     return req.build_absolute_uri(url) if req else url
    def get_url(self, obj):
        try:
            # Lấy URL gốc từ thư viện (thường mặc định là /image/ hoặc /auto/)
            url = obj.file.url
            
            # ✅ FIX QUAN TRỌNG: Ép kiểu URL theo media_type trong Database
            if obj.media_type == 'video':
                # Nếu DB bảo là video, ta thay thế mọi tiền tố sai thành /video/
                url = url.replace("/image/upload/", "/video/upload/")
                url = url.replace("/auto/upload/", "/video/upload/")
            else:
                # Nếu là ảnh
                url = url.replace("/auto/upload/", "/image/upload/")
            
            # Logic build absolute URI (giữ nguyên của bạn)
            req = self.context.get("request")
            if req and not url.startswith("http"):
                return req.build_absolute_uri(url)
            return url
            
        except Exception as e:
            print(f"Error getting URL: {e}")
            return None
    def get_type(self, obj):
        name = (obj.file.name or "").lower()
        ct = getattr(obj.file, "content_type", "") or ""
        return "video" if (ct.startswith("video") or name.endswith((".mp4", ".mov", ".webm", ".mkv"))) else "image"


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    author_id = serializers.IntegerField(source="author.id", read_only=True)  # ✅ THÊM
    avatar = serializers.SerializerMethodField()
    time = serializers.DateTimeField(source="created_at", format="%Y-%m-%dT%H:%M:%S%z")
    likes = serializers.SerializerMethodField()
    reaction_counts = serializers.SerializerMethodField()  # ✅ THÊM
    reaction = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            "id", "user", "author_id", "avatar", "text", "time",  # ✅ THÊM author_id
            "likes", "reaction_counts", "reaction", "replies"      # ✅ THÊM reaction_counts
        ]
    
    def get_user(self, o):
        return o.author.get_full_name() or o.author.username or o.author.email
    
    def get_avatar(self, o):
        try:
            url = o.author.avatar.url
            req = self.context.get("request")
            return req.build_absolute_uri(url) if req else url
        except Exception:
            return None
    
    def get_likes(self, o):
        """Tổng số reactions (tất cả loại)"""
        return o.reactions.count()
    
    # ✅ THÊM: Đếm reactions theo từng loại
    def get_reaction_counts(self, o):
        """Trả về số lượng reactions theo từng loại"""
        agg = o.reactions.values("type").order_by().annotate(count=models.Count("id"))
        return {x["type"]: x["count"] for x in agg}
    
    # ✅ SỬA: Trả về đúng icon/label
    def get_reaction(self, o):
        """Reaction của user hiện tại"""
        req = self.context.get("request")
        if not req or not req.user.is_authenticated:
            return None
        
        r = o.reactions.filter(user=req.user).first()
        if not r:
            return None
        
        display = get_reaction_display(r.type)
        return {
            "type": r.type,
            "icon": display['icon'],
            "label": display['label']
        }
    
    def get_replies(self, o):
        """Nested replies (comments con)"""
        children = o.replies.order_by("created_at")
        return CommentSerializer(children, many=True, context=self.context).data


class PostSerializer(serializers.ModelSerializer):
    author = UserBasicSerializer(read_only=True)
    images = PostMediaSerializer(source="media", many=True, read_only=True)
    time = serializers.DateTimeField(source="created_at", format="%Y-%m-%dT%H:%M:%S%z")
    content = serializers.SerializerMethodField()
    reaction_counts = serializers.SerializerMethodField()
    
    # 👇 Giữ cái cũ (trả về object {type, icon...})
    my_reaction = serializers.SerializerMethodField()
    
    # ✅ THÊM CÁI MỚI: Trả về string đơn giản ("like", "love"...) để khớp với logic Frontend
    user_reaction = serializers.SerializerMethodField() 
    
    comments_count = serializers.IntegerField(source="comments.count", read_only=True)

    class Meta:
        model = Post
        fields = [
            "id", "author", "time", "content", "images",
            "reaction_counts", 
            "my_reaction",      # Object đầy đủ
            "user_reaction",    # String đơn giản (quan trọng cho logic check like)
            "comments_count", "kind"
        ]

    def get_content(self, o):
        return o.content_medical if o.kind == "medical" else (o.content_text or "")
    
    def get_reaction_counts(self, o):
        agg = o.reactions.values("type").order_by().annotate(count=models.Count("id"))
        return {x["type"]: x["count"] for x in agg}
    
    # ✅ Hàm mới: Trả về string reaction type (ví dụ: "like")
    def get_user_reaction(self, o):
        req = self.context.get("request")
        if not req or not req.user.is_authenticated:
            return None
        
        # Cách tối ưu: Tìm trong prefetch (nếu view đã prefetch)
        # Nếu view chưa prefetch, nó sẽ query DB (chấp nhận được với số lượng nhỏ)
        for reaction in o.reactions.all():
            if reaction.user_id == req.user.id:
                return reaction.type # Trả về string: "like", "love", ...
        return None

    # Hàm cũ: Trả về object { type, icon, label }
    def get_my_reaction(self, o):
        req = self.context.get("request")
        if not req or not req.user.is_authenticated:
            return None
        
        # Tận dụng logic tìm kiếm giống bên trên
        rtype = self.get_user_reaction(o) 
        if not rtype:
            return None
        
        display = get_reaction_display(rtype)
        return {
            "type": rtype,
            "icon": display['icon'],
            "label": display['label']
        }
