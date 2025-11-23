from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from cloudinary_storage.storage import MediaCloudinaryStorage
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
    kind = models.CharField(max_length=20, default="normal")  # normal | medical
    content_text = models.TextField(blank=True, null=True)
    content_medical = models.JSONField(blank=True, null=True) 
    visibility = models.CharField(max_length=20, default="public")
    created_at = models.DateTimeField(default=timezone.now)

class PostMedia(models.Model):
    # post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    # file = models.FileField(
    #     upload_to="posts/",
    #     storage=MediaCloudinaryStorage(),
    #     validators=[FileExtensionValidator(allowed_extensions=['jpg','jpeg','png','gif','mp4','mov','webm'])]
    # )
    # media_type = models.CharField(max_length=10, choices=[('image','image'), ('video','video')], blank=True)
    # created_at = models.DateTimeField(default=timezone.now)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    
    # 🔥 2. SỬA LẠI TRƯỜNG FILE: Dùng MixedMediaCloudinaryStorage
    file = models.FileField(
        upload_to="posts/",
        storage=MixedMediaCloudinaryStorage(), # ✅ Thay MediaCloudinaryStorage bằng cái này
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
