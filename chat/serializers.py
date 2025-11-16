from rest_framework import serializers
from .models import Conversation, Message
from accounts.models import User

class UserBasicSerializer(serializers.ModelSerializer):
    """Serializer cơ bản cho User (dùng trong chat)"""
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()  # ✅ SỬA: Dùng SerializerMethodField
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'avatar', 'name']
    
    def get_name(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name or obj.username
    
    def get_avatar(self, obj):
        """✅ Trả về full URL cho avatar"""
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url'):
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            # Fallback nếu không có request context
            return obj.avatar.url
        return None

class MessageSerializer(serializers.ModelSerializer):
    """Serializer cho Message"""
    sender = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'text', 'created_at', 'is_read']
        read_only_fields = ['id', 'sender', 'created_at']
    
    def to_representation(self, instance):
        """Ensure consistent output format"""
        data = super().to_representation(instance)
        
        # ✅ Đảm bảo luôn có sender object đầy đủ
        if not data.get('sender') or not isinstance(data.get('sender'), dict):
            request = self.context.get('request')
            avatar_url = None
            if instance.sender.avatar:
                if request:
                    avatar_url = request.build_absolute_uri(instance.sender.avatar.url)
                else:
                    avatar_url = instance.sender.avatar.url
            
            data['sender'] = {
                'id': instance.sender.id,
                'username': instance.sender.username,
                'name': instance.sender.get_full_name() or instance.sender.username,
                'avatar': avatar_url
            }
        
        return data

class ConversationSerializer(serializers.ModelSerializer):
    """Serializer cho Conversation"""
    participants = UserBasicSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = ['id', 'participants', 'last_message', 'unread_count', 'created_at', 'updated_at']
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        return MessageSerializer(last_msg, context=self.context).data if last_msg else None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0