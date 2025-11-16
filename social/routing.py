# social/routing.py
from django.urls import re_path
from . import consumers
from chat import consumers as chat_consumers

websocket_urlpatterns = [
    re_path(r"ws/feed/$", consumers.FeedConsumer.as_asgi()),
    re_path(r"ws/chat/$", chat_consumers.ChatConsumer.as_asgi()),  
]
