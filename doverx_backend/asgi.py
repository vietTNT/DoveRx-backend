"""
ASGI config for doverx_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

# ✅ Set DJANGO_SETTINGS_MODULE TRƯỚC KHI import bất cứ thứ gì
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doverx_backend.settings')

# ✅ Get Django ASGI app TRƯỚC để Django setup xong
django_asgi_app = get_asgi_application()

# ✅ Import channels và middleware SAU KHI Django đã setup
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from social.middleware import JWTAuthMiddleware
from social.routing import websocket_urlpatterns as social_ws_urls
from chat.routing import websocket_urlpatterns as chat_ws_urls
# ✅ Tạo application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        AuthMiddlewareStack(
          URLRouter(chat_ws_urls + social_ws_urls)
        )
    ),
})
