from django.conf import settings
from django.db import models
from django.utils import timezone
from cloudinary_storage.storage import MediaCloudinaryStorage
REACTION_CHOICES = [
    ("like", "Like"), ("love", "Love"), ("haha", "Haha"),
    ("wow", "Wow"), ("sad", "Sad"), ("angry", "Angry"), ("care", "Care"),
]

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    kind = models.CharField(max_length=20, default="normal")  # normal | medical
    content_text = models.TextField(blank=True, null=True)
    content_medical = models.JSONField(blank=True, null=True)  # dùng cho form “Hỏi bác sĩ”
    visibility = models.CharField(max_length=20, default="public")
    created_at = models.DateTimeField(default=timezone.now)

class PostMedia(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(
        upload_to="posts/",
        storage=MediaCloudinaryStorage()    
    )
    media_type = models.CharField(max_length=10)

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
