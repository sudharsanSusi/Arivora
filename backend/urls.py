from django.urls import path
from . import views

urlpatterns = [
    path('send-otp/', views.send_otp, name='send_otp'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('check-user/', views.check_user, name='check_user'),
    path('validate-session/', views.validate_session_view, name='validate_session'),
    path('logout/', views.logout_user, name='logout'),
    path('chat/', views.chat_with_gemini, name='chat'),

    # Chat history endpoints
    path('chat-sessions/create/', views.create_session, name='create_session'),
    path('chat-sessions/list/', views.list_sessions, name='list_sessions'),
    path('chat-sessions/messages/', views.get_session_messages, name='get_session_messages'),
    path('chat-sessions/save-message/', views.save_chat_message, name='save_chat_message'),
    path('chat-sessions/delete/', views.delete_session, name='delete_session'),
]
