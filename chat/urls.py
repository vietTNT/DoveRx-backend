from django.urls import path
from . import views

urlpatterns = [
    path('conversations/', views.get_conversations, name='get-conversations'),
    path('conversations/with/<int:user_id>/', views.get_conversation_with_user, name='get-conversation-with-user'),  # ✅ THÊM
     # Messages
    path('conversations/<int:conversation_id>/messages/', views.get_messages, name='get_messages'),  # ✅ ĐÚNG
    path('messages/mark_as_read/', views.mark_messages_as_read, name='mark_as_read'),
]