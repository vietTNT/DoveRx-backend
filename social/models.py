from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from cloudinary_storage.storage import MediaCloudinaryStorage
from django.conf import settings
REACTION_CHOICES = [
    ("like", "Like"), ("love", "Love"), ("haha", "Haha"),
    ("wow", "Wow"), ("sad", "Sad"), ("angry", "Angry"), ("care", "Care"),
]
class MixedMediaCloudinaryStorage(MediaCloudinaryStorage):
    def _get_resource_type(self, name):
        """
        Ghi đè để Cloudinary tự động nhận diện là video hay image
        """
        return 'auto'
class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    kind = models.CharField(max_length=20, default="normal")  
    content_text = models.TextField(blank=True, null=True)
    content_medical = models.JSONField(blank=True, null=True) 
    visibility = models.CharField(max_length=20, default="public")
    created_at = models.DateTimeField(default=timezone.now)

class PostMedia(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    
    file = models.FileField(
        upload_to="posts/",
        storage=MixedMediaCloudinaryStorage(), 
        validators=[FileExtensionValidator(allowed_extensions=['jpg','jpeg','png','gif','mp4','mov','webm'])]
    )
    
    media_type = models.CharField(max_length=10, choices=[('image','image'), ('video','video')], blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    def save(self, *args, **kwargs):
        if self.file and not self.media_type:
            content_type = getattr(self.file, 'content_type', '') or ''
            if content_type.startswith('image/'):
                self.media_type = 'image'
            elif content_type.startswith('video/'):
                self.media_type = 'video'
            else:
                ext = (self.file.name.split('.')[-1] or '').lower()
                if ext in ('mp4','mov','webm'):
                    self.media_type = 'video'
                else:
                    self.media_type = 'image'
        super().save(*args, **kwargs)

class PostReaction(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ("post", "user")

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

class CommentReaction(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ("comment", "user")

class Share(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
class Notification(models.Model):
    TYPES = (
        ('post_react', 'Thả cảm xúc bài viết'),
        ('new_comment', 'Bình luận mới'),
        ('comment_react', 'Thả cảm xúc bình luận'),
        ('new_post', 'Bài đăng mới từ bạn bè'),
        ('friend_request', 'Lời mời kết bạn'),
        ('friend_accept', 'Chấp nhận kết bạn'),
    )

    #  Thay User bằng settings.AUTH_USER_MODEL
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications') 
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_notifications')
    
    notification_type = models.CharField(max_length=20, choices=TYPES)
    
    # Các trường liên kết (Foreign Key) khác giữ nguyên, 
    # nhưng nếu Post/Comment nằm cùng file này thì dùng tên class trực tiếp hoặc chuỗi 'Post'
    post = models.ForeignKey('Post', on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey('Comment', on_delete=models.CASCADE, null=True, blank=True)
    
    text = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif for {self.recipient}: {self.text}"