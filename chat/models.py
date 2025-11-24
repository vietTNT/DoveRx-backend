from django.db import models
from accounts.models import User
from .storage import MixedMediaCloudinaryStorage
class Conversation(models.Model):
    """
    Model đại diện cho cuộc trò chuyện giữa 2 người dùng
    """
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        participant_names = ', '.join([user.username for user in self.participants.all()[:2]])
        return f"Conversation {self.id}: {participant_names}"
    
    def get_other_user(self, current_user):
        """
        Lấy người dùng còn lại trong conversation (không phải current_user)
        
        Args:
            current_user: User object đang đăng nhập
            
        Returns:
            User object của người còn lại, hoặc None nếu không tìm thấy
        """
        participants = self.participants.exclude(id=current_user.id).first()
        return participants


class Message(models.Model):
    """
    Model đại diện cho tin nhắn trong conversation
    """
    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)

    attachment = models.FileField(
        upload_to='chat_attachments/',     
        storage=MixedMediaCloudinaryStorage(),
        blank=True, 
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.sender.username}: {self.text[:50]}"
