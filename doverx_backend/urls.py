
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from django.http import HttpResponse 
# 👇 Thêm hàm này để hiển thị trang chủ
def home(request):
    return HttpResponse("<h1>🚀 DoveRx Backend is Running Successfully!</h1>") 
urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),

    # Các API chính
    path('api/accounts/', include('accounts.urls')),  # Đăng ký, đăng nhập, hồ sơ, v.v.
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path("api/social/", include("social.urls")),
    path('api/chat/', include('chat.urls')),
]

# Cho phép truy cập ảnh avatar trong MEDIA
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
