from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Max
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer

class ConversationViewSet(viewsets.ModelViewSet):
    """API cho Conversations"""
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Lấy danh sách cuộc trò chuyện của user hiện tại"""
        return Conversation.objects.filter(
            participants=self.request.user
        ).prefetch_related('participants', 'messages')
    
    @action(detail=False, methods=['post'])
    def get_or_create(self, request):
        """Lấy hoặc tạo conversation với user khác"""
        other_user_id = request.data.get('user_id')
        
        if not other_user_id:
            return Response(
                {'error': 'user_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Tìm conversation có 2 người này
        conversation = Conversation.objects.filter(
            participants=request.user
        ).filter(
            participants=other_user_id
        ).annotate(
            participant_count=models.Count('participants')
        ).filter(
            participant_count=2
        ).first()
        
        if not conversation:
            # Tạo mới
            conversation = Conversation.objects.create()
            conversation.participants.add(request.user, other_user_id)
        
        serializer = self.get_serializer(conversation)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet):
    """API cho Messages"""
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Lấy tin nhắn của conversation"""
        conversation_id = self.request.query_params.get('conversation')
        
        if conversation_id:
            # Kiểm tra user có trong conversation không
            conversation = Conversation.objects.filter(
                id=conversation_id,
                participants=self.request.user
            ).first()
            
            if conversation:
                return Message.objects.filter(
                    conversation=conversation
                ).select_related('sender')
        
        return Message.objects.none()
    
    def perform_create(self, serializer):
        """Tạo tin nhắn mới"""
        serializer.save(sender=self.request.user)
    
    @action(detail=False, methods=['post'])
    def mark_as_read(self, request):
        """Đánh dấu tin nhắn đã đọc"""
        conversation_id = request.data.get('conversation_id')
        
        if not conversation_id:
            return Response(
                {'error': 'conversation_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Đánh dấu tất cả tin nhắn chưa đọc của conversation
        Message.objects.filter(
            conversation_id=conversation_id,
            is_read=False
        ).exclude(
            sender=request.user
        ).update(is_read=True)
        
        return Response({'status': 'marked as read'})