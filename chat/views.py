from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q, Max, Count
from django.db import models
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from accounts.models import User
from rest_framework.permissions import IsAuthenticated


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversations(request):
    """
    Lấy danh sách tất cả conversations của user hiện tại
    
    GET /api/chat/conversations/
    
    Returns:
    [
        {
            "id": 1,
            "participants": [...],
            "last_message": {...},
            "unread_count": 5
        }
    ]
    """
    try:
        conversations = Conversation.objects.filter(
            participants=request.user
        ).prefetch_related('participants').order_by('-updated_at')
        
        serializer = ConversationSerializer(
            conversations, 
            many=True, 
            context={'request': request}
        )
        
        return Response(serializer.data)
        
    except Exception as e:
        print(f"❌ [get_conversations] Error: {e}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation_with_user(request, user_id):
    """
    Lấy hoặc tạo conversation giữa current user và user_id
    
    GET /api/chat/conversations/with/<user_id>/
    
    Returns:
    {
        "id": 1,
        "participants": [...],
        "last_message": {...}
    }
    """
    try:
        other_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    print(f"🔍 [get_conversation_with_user] Looking for conversation")
    print(f"   Current user: {request.user.username} (ID: {request.user.id})")
    print(f"   Other user: {other_user.username} (ID: {other_user.id})")
    
    # ✅ SỬA: Query đúng để tìm conversation
    # Tìm conversation có CẢ 2 user và chỉ có 2 user
    conversations = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    )
    
    # Lọc những conversation có đúng 2 participants
    conversation = None
    for conv in conversations:
        if conv.participants.count() == 2:
            conversation = conv
            break
    
    # ✅ CHỈ TẠO MỚI NẾU CHƯA CÓ
    if not conversation:
        print(f"⚠️ [get_conversation_with_user] NO EXISTING CONVERSATION FOUND!")
        print(f"⚠️ Creating NEW conversation between {request.user.username} and {other_user.username}")
        
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)
        conversation.save()
        
        print(f"✅ [get_conversation_with_user] Created conversation {conversation.id}")
    else:
        print(f"✅ [get_conversation_with_user] Found EXISTING conversation {conversation.id}")
        print(f"   Participants: {[p.username for p in conversation.participants.all()]}")
    
    serializer = ConversationSerializer(conversation, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_messages(request, conversation_id):
    """
    Lấy danh sách tin nhắn trong conversation
    
    GET /api/chat/conversations/<conversation_id>/messages/
    """
    try:
        print(f"📩 [get_messages] User {request.user.id} requesting messages for conversation {conversation_id}")
        
        # Kiểm tra conversation có tồn tại và user có quyền truy cập không
        try:
            conversation = Conversation.objects.prefetch_related('participants').get(
                id=conversation_id,
                participants=request.user
            )
        except Conversation.DoesNotExist:
            print(f"❌ [get_messages] Conversation {conversation_id} not found or user has no access")
            return Response(
                {'error': 'Conversation not found or you do not have access'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Lấy tin nhắn
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        messages = Message.objects.filter(
            conversation_id=conversation_id
        ).select_related('sender').order_by('-created_at')[offset:offset+limit]
        
        # Đảo ngược để tin nhắn cũ nhất ở trên
        messages = list(reversed(messages))
        
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        
        print(f"✅ [get_messages] Returning {len(messages)} messages")
        return Response(serializer.data)
        
    except Exception as e:
        print(f"❌ [get_messages] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_messages_as_read(request):
    """
    Đánh dấu tất cả tin nhắn trong conversation là đã đọc
    
    POST /api/chat/messages/mark_as_read/
    Body: { "conversation_id": 1 }
    
    Returns:
    {
        "success": true,
        "marked_count": 5
    }
    """
    try:
        conversation_id = request.data.get('conversation_id')
        
        if not conversation_id:
            return Response(
                {'error': 'conversation_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Kiểm tra user có quyền truy cập conversation không
        conversation = Conversation.objects.filter(
            id=conversation_id,
            participants=request.user
        ).first()
        
        if not conversation:
            return Response(
                {'error': 'Conversation not found or access denied'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Đánh dấu đã đọc (chỉ tin nhắn từ người khác)
        marked_count = Message.objects.filter(
            conversation_id=conversation_id,
            is_read=False
        ).exclude(sender=request.user).update(is_read=True)
        
        print(f"✅ [mark_messages_as_read] Marked {marked_count} messages as read in conversation {conversation_id}")
        
        return Response({
            'success': True,
            'marked_count': marked_count
        })
        
    except Exception as e:
        print(f"❌ [mark_messages_as_read] Error: {e}")
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

