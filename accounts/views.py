from django.shortcuts import render
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes
from .serializers import RegisterSerializer, UserSerializer, FriendshipSerializer
from django.core.mail import send_mail
from django.conf import settings
import random
import datetime
from django.utils import timezone
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .serializers import CustomTokenObtainPairSerializer
from django.db.models import Q
from .models import Friendship, UserStatus 
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils.text import slugify
import uuid
User = get_user_model()


# Đăng ký người dùng
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


#  Lấy thông tin hồ sơ người dùng hiện tại
class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)



from rest_framework.parsers import MultiPartParser, FormParser
class UpdateProfileAPIView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser] 
    def get_object(self):
        return self.request.user

    def put(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # trả về với context để build absolute avatar URL
            return Response(UserSerializer(user, context={"request": request}).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DoctorRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        print("📩 Dữ liệu nhận từ frontend:", data)

        try:
       
            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                print("❌ Thiếu thông tin cơ bản")
                return Response({"error": "Thiếu email hoặc mật khẩu."},
                                status=status.HTTP_400_BAD_REQUEST)

            if User.objects.filter(email=email).exists():
                print("❌ Email đã tồn tại:", email)
                return Response( {"error": "Email đã tồn tại trong hệ thống."},
                                status=status.HTTP_400_BAD_REQUEST,)
            # 3. Tự động sinh username từ email
         
            base_username = slugify(email.split('@')[0])
            unique_suffix = str(uuid.uuid4())[:4] # Thêm 4 ký tự ngẫu nhiên để tránh trùng
            username = f"{base_username}_{unique_suffix}"
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
                role="doctor",
                doctor_type=data.get("doctorType"),
                specialty=data.get("specialty", ""),
                workplace=data.get("workplace", ""),
                phone=data.get("phone", ""),
                license_number=data.get("license_number", ""),
            )
         

           
            user.generate_otp()
          

           
            send_mail(
                subject="🔐 Mã xác nhận tài khoản DoveRx của bạn",
                message=f"Xin chào {user.first_name or user.username},\n\n"
                        f"Mã xác nhận của bạn là: {user.otp_code}\n"
                        f"Mã có hiệu lực trong 10 phút.\n\nCảm ơn bạn đã đăng ký DoveRx!",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

        
            return Response({"message": "Đăng ký thành công! Vui lòng kiểm tra email để xác minh tài khoản."},
                            status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            print("❌ Lỗi khi đăng ký bác sĩ:", e)
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")

        try:
            user = User.objects.get(email=email)

            if not user.otp_code:
                return Response({"error": "Tài khoản chưa yêu cầu OTP."}, status=status.HTTP_400_BAD_REQUEST)

            if user.otp_code != otp:
                return Response({"error": "Mã xác nhận không đúng."}, status=status.HTTP_400_BAD_REQUEST)

            if timezone.now() > user.otp_expiry:
                return Response({"error": "Mã xác nhận đã hết hạn."}, status=status.HTTP_400_BAD_REQUEST)

            user.is_verified = True
            user.otp_code = None
            user.save()

            return Response({"message": "Xác minh thành công! Tài khoản đã được kích hoạt."}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "Không tìm thấy tài khoản này."}, status=status.HTTP_404_NOT_FOUND)

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer



@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_avatar(request):
    """Xóa avatar về mặc định"""
    user = request.user
    
    # Xóa file avatar cũ
    if user.avatar:
        user.avatar.delete(save=False)
    
    user.avatar = None
    user.save()
    
    return Response({
        'message': 'Avatar removed successfully',
        'avatar': None
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_users(request):
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return Response({'results': []})
    
    current_user = request.user
    
    # 1. Lấy list Users
    users_qs = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query)
    ).exclude(id=current_user.id)[:10]
    target_users = list(users_qs) 
    
    # Nếu không có user nào thì trả về rỗng luôn (đỡ tốn công query Friendship)
    if not target_users:
        return Response({'results': []})

    # Lấy danh sách ID thuần (Python list)
    target_user_ids = [u.id for u in target_users]
    # 2. Lấy TẤT CẢ Friendship liên quan đến list users này trong 1 lần query
    friendships = Friendship.objects.filter(
        (Q(from_user=current_user) & Q(to_user_id__in=target_user_ids)) |
        (Q(from_user_id__in=target_user_ids) & Q(to_user=current_user))
    )

    # 3. Tạo Map để tra cứu nhanh 
    friend_map = {}
    for f in friendships:
        if f.from_user_id == current_user.id:
            friend_map[f.to_user_id] = f.status  # Mình gửi
        else:
            friend_map[f.from_user_id] = f'received_{f.status}' # Họ gửi

    results = []
    for user in target_users:
        status = friend_map.get(user.id)
        
        avatar_url = None
        try:
            if user.avatar:
                avatar_url = user.avatar.url
        except:
            pass
        full_name = f"{user.first_name} {user.last_name}".strip()
        results.append({
            'id': user.id,
            'username': user.username,
            'name': full_name or user.username,
            'email': user.email,
            'avatar': avatar_url,
            'role': user.role,
            'friendship_status': status
        })
    
    return Response({'results': results})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_friend_requests(request):
  
    current_user = request.user
    
    # Lấy các lời mời kết bạn mà user này nhận được
    received_requests = Friendship.objects.filter(
        to_user=current_user,
        status='pending'
    ).select_related('from_user')
    
    requests = []
    for friendship in received_requests:
        user = friendship.from_user
        full_name = f"{user.first_name} {user.last_name}".strip()
        
        requests.append({
            'id': friendship.id,
            'from_user': {
                'id': user.id,
                'username': user.username,
                'name': full_name or user.username,
                'avatar':user.avatar.url if user.avatar else None
            },
            'created_at': friendship.created_at
        })
    
    return Response(requests)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_friend_request(request):
    """
    Gửi lời mời kết bạn & Bắn thông báo Realtime
    Body: { "to_user_id": 123 }
    """
    to_user_id = request.data.get('to_user_id')
    
    if not to_user_id:
        return Response({'error': 'to_user_id is required'}, status=400)
    
    if int(to_user_id) == request.user.id:
        return Response({'error': 'Cannot send friend request to yourself'}, status=400)
    
    try:
        to_user = User.objects.get(id=to_user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    
    # Kiểm tra/Tạo lời mời (Dùng get_or_create để an toàn hơn)
    friendship, created = Friendship.objects.get_or_create(
        from_user=request.user,
        to_user=to_user,
        defaults={'status': 'pending'}
    )

    # Nếu đã tồn tại từ trước
    if not created:
        if friendship.status == 'rejected':
            # Nếu từng bị từ chối, cho phép gửi lại
            friendship.status = 'pending'
            friendship.save()
        elif friendship.status == 'accepted':
            return Response({'message': 'Already friends'}, status=400)
        elif friendship.status == 'pending':
            return Response({'message': 'Friend request already sent'}, status=400)

    # ==================================================================
    # 2. GỬI WEBSOCKET (Code mới thêm)
    # ==================================================================
    try:
        channel_layer = get_channel_layer()
        
        # Chuẩn bị dữ liệu hiển thị cho người nhận
        # (Avatar, Tên người gửi để hiện trên thông báo)
        user_avatar = None
        if request.user.avatar:
            try:
                user_avatar = request.user.avatar.url
                # Fix lỗi URL nếu cần (giống bên chat)
                if user_avatar.startswith("http"):
                    user_avatar = user_avatar.replace("http:", "https:")
            except: pass

        request_data = {
            "id": friendship.id,
            "from_user": {
                "id": request.user.id,
                "name": f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                "avatar": user_avatar
            },
            "created_at": friendship.created_at.isoformat()
        }

        # Gửi đến group của người nhận: "user_{ID}"
        async_to_sync(channel_layer.group_send)(
            f"user_{to_user.id}", 
            {
                "type": "send_notification", # Hàm xử lý trong ChatConsumer
                "data": {
                    "event": "friend_request_received", # Frontend Navbar sẽ bắt event này
                    "request_data": request_data
                }
            }
        )
        print(f"📡 [Socket] Đã gửi thông báo kết bạn tới user_{to_user.id}")

    except Exception as e:
        print(f"❌ [Socket Error] Không gửi được thông báo: {e}")
    # ==================================================================

    return Response({
        'message': 'Friend request sent',
        'friendship_id': friendship.id
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_friend_request(request):
    """
    Chấp nhận lời mời kết bạn
    Body: { "from_user_id": 123 }
    """
    from_user_id = request.data.get('from_user_id')
    
    if not from_user_id:
        return Response(
            {'error': 'from_user_id is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        friendship = Friendship.objects.get(
            from_user_id=from_user_id,
            to_user=request.user,
            status='pending'
        )
    except Friendship.DoesNotExist:
        return Response(
            {'error': 'Friend request not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    friendship.status = 'accepted'
    friendship.save()
    
    friend = friendship.from_user
    full_name = f"{friend.first_name} {friend.last_name}".strip()
    
    # Lấy online status
    is_online = False
    try:
        if hasattr(friend, 'status'):
            is_online = friend.status.is_online
    except Exception:
        pass
    
    return Response({
        'message': 'Friend request accepted',
        'friendship_id': friendship.id,
        'friend': {
            'id': friend.id,
            'username': friend.username,
            'name': full_name or friend.username,
            'email': friend.email,
            # 'avatar': request.build_absolute_uri(friend.avatar.url) if friend.avatar else None,
            'avatar':friend.avatar.url if friend.avatar else None,
            'role': friend.role,
            'online': is_online
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_friend_request(request):
    """
    Từ chối lời mời kết bạn
    Body: { "from_user_id": 123 }
    """
    from_user_id = request.data.get('from_user_id')
    
    if not from_user_id:
        return Response(
            {'error': 'from_user_id is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        friendship = Friendship.objects.get(
            from_user_id=from_user_id,
            to_user=request.user,
            status='pending'
        )
    except Friendship.DoesNotExist:
        return Response(
            {'error': 'Friend request not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    friendship.delete()
    
    return Response({
        'message': 'Friend request rejected',
        'from_user_id': from_user_id
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_friends(request):
    """
    Lấy danh sách bạn bè (status = accepted)
    """
    current_user = request.user
    
    friendships = Friendship.objects.filter(
        Q(from_user=current_user) | Q(to_user=current_user),
        status='accepted'
    ).select_related('from_user', 'to_user', 'from_user__status', 'to_user__status')
    
    friends = []
    for friendship in friendships:
        friend = friendship.to_user if friendship.from_user == current_user else friendship.from_user
        
        full_name = f"{friend.first_name} {friend.last_name}".strip()
        
        # Lấy trạng thái online
        is_online = False
        try:
            if hasattr(friend, 'status'):
                is_online = friend.status.is_online
        except Exception as e:
            print(f"⚠️ [get_friends] Cannot get online status for user {friend.id}: {e}")
        
        friends.append({
            'id': friend.id,
            'username': friend.username,
            'name': full_name or friend.username,
            'email': friend.email,
            # 'avatar': request.build_absolute_uri(friend.avatar.url) if friend.avatar else None,
             'avatar':friend.avatar.url if friend.avatar else None,
            'role': friend.role,
            'online': is_online
        })
    
    return Response(friends)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_users_list(request):
    """
    Lấy danh sách tất cả users (trừ chính mình)
    Dùng cho sidebar chat contacts
    """
    current_user = request.user
    
    #  Dùng select_related để tối ưu query
    users = User.objects.exclude(id=current_user.id).select_related('status')
    
    users_list = []
    for user in users:
        full_name = f"{user.first_name} {user.last_name}".strip()
        
        # Lấy trạng thái online
        is_online = False
        try:
            if hasattr(user, 'status'):
                is_online = user.status.is_online
        except Exception as e:
            print(f"⚠️ [get_users_list] Cannot get online status for user {user.id}: {e}")
        
        users_list.append({
            'id': user.id,
            'name': full_name or user.username or user.email.split('@')[0],
            'email': user.email,
           
            'avatar':user.avatar.url if user.avatar else None,
            'role': user.role,
            'online': is_online  # Lấy từ database
        })
    
    return Response(users_list)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_by_id(request, user_id):
    """
    Lấy thông tin user theo ID
    Bao gồm cả friendship status với current user
    """
    try:
        target_user = User.objects.select_related('status').get(id=user_id)  #  THÊM select_related
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    current_user = request.user
    
    # Check friendship status
    sent_request = Friendship.objects.filter(
        from_user=current_user,
        to_user=target_user
    ).first()
    
    received_request = Friendship.objects.filter(
        from_user=target_user,
        to_user=current_user
    ).first()
    
    friendship_status = None
    if sent_request:
        friendship_status = sent_request.status
    elif received_request:
        friendship_status = 'received_' + received_request.status
    
    full_name = f"{target_user.first_name} {target_user.last_name}".strip()
    
    #  Lấy online status
    is_online = False
    try:
        if hasattr(target_user, 'status'):
            is_online = target_user.status.is_online
    except Exception:
        pass
    
    user_data = {
        'id': target_user.id,
        'username': target_user.username,
        'name': full_name or target_user.username,
        'email': target_user.email,
       
        'avatar':target_user.avatar.url if target_user.avatar else None,
        'role': target_user.role,
        'bio': getattr(target_user, 'bio', None),
        'specialty': getattr(target_user, 'specialty', None) if target_user.role == 'doctor' else None,
        'workplace': getattr(target_user, 'workplace', None) if target_user.role == 'doctor' else None,
        'friendship_status': friendship_status,
        'online': is_online  
    }
    
    return Response(user_data)