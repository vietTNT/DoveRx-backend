from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView,
    DoctorRegisterView,
    VerifyOTPView,
    ProfileAPIView,
    UpdateProfileAPIView,
    CustomLoginView,
    remove_avatar,
)
from . import views
from .views_google import GoogleLoginAPIView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("register/doctor/", DoctorRegisterView.as_view(), name="register-doctor"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("google-login/", GoogleLoginAPIView.as_view(), name="google-login"),
    path("profile/", ProfileAPIView.as_view(), name="profile"),
    path("update-profile/", UpdateProfileAPIView.as_view(), name="update-profile"),
    path('remove-avatar/', remove_avatar, name='remove_avatar'),
     # Users List
    path('users/', views.get_users_list, name='users-list'),
    
    # ✅ THÊM DÒNG NÀY
    path('users/<int:user_id>/', views.get_user_by_id, name='get-user-by-id'),
    # Friend System
    path('search/', views.search_users, name='search-users'),
    path('friends/', views.get_friends, name='get-friends'),
    path('friends/requests/', views.get_friend_requests, name='get-friend-requests'),
    path('friends/send/', views.send_friend_request, name='send-friend-request'),
    path('friends/accept/', views.accept_friend_request, name='accept-friend-request'),
    path('friends/reject/', views.reject_friend_request, name='reject-friend-request'),
]
