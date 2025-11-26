from rest_framework import serializers
from .models import Conversation, Message
from accounts.models import User
import mimetypes


class UserBasicSerializer(serializers.ModelSerializer):
    """Serializer cơ bản cho User (dùng trong chat)"""
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'avatar', 'name']
    
    def get_name(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name or obj.username
    
    def get_avatar(self, obj):
        if obj.avatar:
            try:
                if hasattr(obj.avatar, 'url'):
                    url = obj.avatar.url
                    
                    # 1. Ép về HTTPS
                    if url.startswith("http:"):
                        url = url.replace("http:", "https:")
                    
                    # 2. XỬ LÝ FOLDER AVATARS (Logic bạn yêu cầu)
                    if "cloudinary.com" in url:
                        
                        if "avatars/" in url and "/media/" not in url:
                            url = url.replace("/avatars/", "/media/avatars/")
                        
                       
                        elif "/media/" in url and "avatars/" not in url:
                            url = url.replace("/media/", "/")
                    
                    return url
            except:
                pass
            
            # Fallback
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class MessageSerializer(serializers.ModelSerializer):
    """Serializer cho Message"""
    sender = UserBasicSerializer(read_only=True)
    attachment = serializers.SerializerMethodField()

    class Meta:
        model = Message
        
        fields = ['id', 'conversation', 'sender', 'text', 'attachment', 'created_at', 'is_read']
        read_only_fields = ['id', 'sender', 'created_at']

    def get_attachment(self, obj):
        """
        Trả về object { url: ..., type: ... } và FIX MỌI LỖI URL
        """
        if obj.attachment:
            try:
                # 1. Lấy URL gốc
                file_url = obj.attachment.url
                
                # 2. Fix HTTPS
                if file_url.startswith("http:"):
                    file_url = file_url.replace("http:", "https:")

                # 3. XỬ LÝ FOLDER AVATARS/MEDIA (Áp dụng logic tương tự)
                if "cloudinary.com" in file_url:
                  
                    if "avatars/" in file_url and "/media/" not in file_url:
                        file_url = file_url.replace("/avatars/", "/media/avatars/")
                    
                   
                    elif "/media/" in file_url and "avatars/" not in file_url:
                        file_url = file_url.replace("/media/", "/")

                # 4. Đoán loại file
                try:
                    file_name = obj.attachment.name.lower()
                except:
                    file_name = file_url.lower()

                file_type = 'file'
                if any(ext in file_name for ext in ['.mp4', '.mov', '.avi', '.webm', '.mkv', '.flv']):
                    file_type = 'video'
                elif any(ext in file_name for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff']):
                    file_type = 'image'

                # 5. Fix lỗi URL 'auto' của Cloudinary
                if "/auto/upload/" in file_url:
                    if file_type == 'video':
                        file_url = file_url.replace("/auto/upload/", "/video/upload/")
                    else:
                        file_url = file_url.replace("/auto/upload/", "/image/upload/")
                
                return {
                    "url": file_url,
                    "type": file_type
                }
            except Exception as e:
                print(f"❌ Serializer Error processing attachment: {e}")
                return None
        return None


class ConversationSerializer(serializers.ModelSerializer):
    participants = UserBasicSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'participants', 'last_message', 'unread_count', 'updated_at']

    def get_last_message(self, obj):
     
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return MessageSerializer(last_msg, context=self.context).data
        return None

    def get_unread_count(self, obj):
       
        if hasattr(obj, 'unread_count'):
            return obj.unread_count
            
      
        request = self.context.get('request')
        if request and request.user.is_authenticated:
           
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
            
        return 0