# bảo mật cho WebSocket bằng JWT trong Django Channels
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_key):
    """
     Xác thực JWT token cho WebSocket
    """
    if not token_key:
        return AnonymousUser()
        
    try:
        access_token = AccessToken(token_key)
        user_id = access_token.get("user_id") or access_token.get("id")
        
        if not user_id:
            print("❌ No user_id in token")
            return AnonymousUser()
            
        user = User.objects.get(id=user_id)
        
        #  Kiểm tra user còn active không
        if not user.is_active:
            print(f"❌ User {user.username} is inactive")
            return AnonymousUser()
            
        return user
        
    except (InvalidToken, TokenError) as e:
        print(f"❌ Invalid token: {e}")
        return AnonymousUser()
    except User.DoesNotExist:
        print(f"❌ User not found")
        return AnonymousUser()
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    """
     Middleware xác thực JWT cho WebSocket
    Hỗ trợ:
    - Query param: ?token=xxx
    - Header: Authorization: Bearer xxx
    """
    async def __call__(self, scope, receive, send):
        # Try query string first
        query_string = scope.get("query_string", b"").decode()
        token = None
        
        for param in query_string.split("&"):
            if param.startswith("token="):
                token = param.split("=")[1]
                break

        # Try headers if no query token
        if not token:
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix

        scope["user"] = await get_user_from_token(token)
        
        return await super().__call__(scope, receive, send)
