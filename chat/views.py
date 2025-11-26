from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q, Max, Count
from django.db import models
from django.core.files.storage import default_storage
import cloudinary
import cloudinary.uploader
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from accounts.models import User
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversations(request):
    """
    Lấy danh sách conversations và đếm số tin nhắn chưa đọc chính xác.
    """
    try:
        conversations = Conversation.objects.filter(
            participants=request.user
        ).annotate(
            unread_count=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
            )
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
    
    #  đúng để tìm conversation
    # Tìm conversation có CẢ 2 user và chỉ có 2 user
    conversations = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    )
    
    conversation = Conversation.objects.annotate(
    count=Count('participants')
    ).filter(
    count=2
    ).filter(
    participants=request.user
    ).filter(
        participants=other_user
    ).first()
 
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
    """Đánh dấu tin nhắn là đã đọc (Backend Persistence)"""
    conversation_id = request.data.get('conversation_id')
    
    if not conversation_id:
        return Response({'error': 'conversation_id required'}, status=400)
    
    #  FIX QUAN TRỌNG: Đảm bảo conversation_id là số nguyên hợp lệ
    try:
        conversation_id = int(conversation_id)
    except ValueError:
         return Response({'error': 'Invalid conversation_id format'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Kiểm tra user có quyền truy cập conversation không
        conversation = Conversation.objects.filter(
            id=conversation_id,
            participants=request.user
        ).first()

        if not conversation:
             return Response({'error': 'Conversation not found or access denied'}, status=status.HTTP_404_NOT_FOUND)

        # Update Database: Đánh dấu tất cả tin nhắn từ người khác là đã đọc
        marked_count = Message.objects.filter(
            conversation_id=conversation_id,
            is_read=False
        ).exclude(sender=request.user).update(is_read=True)
        
        print(f"✅ MARKED READ: Conversation {conversation_id}. Count: {marked_count}")
        
        return Response({'success': True, 'marked_count': marked_count})
        
    except Exception as e:
        print(f"❌ Error during mark_messages_as_read: {e}")
        return Response(
            {'error': 'Server error during read update'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_chat_attachment(request):
    """
    API Upload file cho chat -> Đẩy thẳng lên Cloudinary
    POST /api/chat/upload/
    Body: form-data { file: ... }
    """
    try:
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        # 1. Xác định loại file để Cloudinary xử lý tối ưu
        content_type = file_obj.content_type
        resource_type = 'raw' # Mặc định
        file_type = 'file'    # Trả về cho frontend

        if content_type.startswith('image/'):
            resource_type = 'image'
            file_type = 'image'
        elif content_type.startswith('video/'):
            resource_type = 'video'
            file_type = 'video'

        print(f"☁️ [Upload] Đang đẩy file {file_obj.name} lên Cloudinary (Type: {resource_type})...")

        # 2. Upload trực tiếp bằng SDK của Cloudinary
        upload_result = cloudinary.uploader.upload(
            file_obj, 
            folder="chat_attachments", # Thư mục trên Cloudinary
            resource_type=resource_type 
        )

        # 3. Lấy URL HTTPS an toàn
        file_url = upload_result.get('secure_url')
        
        print(f"✅ [Upload] Thành công: {file_url}")

        return Response({
            'url': file_url,
            'type': file_type
        })

    except Exception as e:
        print(f"❌ Upload error: {e}")
        import traceback
        print(traceback.format_exc())
        return Response({'error': str(e)}, status=500)