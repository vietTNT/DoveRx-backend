from django.urls import path
from . import views

urlpatterns = [
    path('conversations/', views.get_conversations, name='get-conversations'),
    path('conversations/with/<int:user_id>/', views.get_conversation_with_user, name='get-conversation-with-user'),  
     # Messages
    path('conversations/<int:conversation_id>/messages/', views.get_messages, name='get_messages'), 
    path('messages/read_sync/', views.mark_messages_as_read, name='mark_as_read'),
    path('upload/', views.upload_chat_attachment, name='chat_upload'),
]