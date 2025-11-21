import os
import dj_database_url
from dotenv import load_dotenv
from pathlib import Path
from datetime import timedelta

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret")

# Mặc định là production để an toàn khi deploy
DJANGO_ENV = os.getenv("DJANGO_ENV", "production")
IS_PRODUCTION = DJANGO_ENV == "production"

# DEBUG: False ở production, True ở dev
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

# -----------------------------
# ALLOWED HOSTS
# -----------------------------
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".railway.app",
    "doverx-backend-production.up.railway.app",
    "doverx.vercel.app",
    "*",
]

# -----------------------------
# APPLICATIONS
# -----------------------------
INSTALLED_APPS = [
    "daphne", # ✅ Daphne nên đứng đầu để handle ASGI
    "channels",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",

    "accounts",
    "social_django",
    "social",
    "chat",
    
    # Các app Cloudinary (sẽ được check kỹ hơn ở dưới, nhưng khai báo ở đây cho chắc)
    "cloudinary",
    "cloudinary_storage",
]

ASGI_APPLICATION = "doverx_backend.asgi.application"

# -----------------------------
# CHANNEL LAYERS (REDIS)
# -----------------------------
# Ưu tiên Redis thật nếu có URL, nếu không thì fallback memory (chỉ dùng cho dev)
if os.getenv("REDIS_URL"):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [os.getenv("REDIS_URL")],
                # Thêm capacity để tránh lỗi full queue khi chat nhiều
                "capacity": 1500,
                "expiry": 10,
            },
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# -----------------------------
# AUTHENTICATION
# -----------------------------
AUTHENTICATION_BACKENDS = (
    "social_core.backends.google.GoogleOAuth2",
    "django.contrib.auth.backends.ModelBackend",
)

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv("GOOGLE_CLIENT_ID")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# -----------------------------
# MIDDLEWARE
# -----------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # ✅ BẮT BUỘC MỞ DÒNG NÀY CHO RAILWAY
    "corsheaders.middleware.CorsMiddleware",  
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "doverx_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# -----------------------------
# DATABASE
# -----------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, conn_health_checks=True)
    }
else:
    # Fallback SQLite/MySQL cho local dev
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# -----------------------------
# STATIC FILES (CSS, JS, Images)
# -----------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Nén file tĩnh cho nhẹ web
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# -----------------------------
# MEDIA & CLOUDINARY (QUAN TRỌNG NHẤT)
# -----------------------------
MEDIA_URL = "/media/"  # Luôn để default, Cloudinary sẽ override khi cần
MEDIA_ROOT = BASE_DIR / "media"

# Lấy cấu hình từ biến môi trường
CLOUDINARY_STORAGE_CONF = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}

# 🔥 LOGIC ÉP BUỘC DÙNG CLOUDINARY NẾU CÓ KEY
if CLOUDINARY_STORAGE_CONF['CLOUD_NAME'] and CLOUDINARY_STORAGE_CONF['API_KEY']:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    
    cloudinary.config(
        cloud_name=CLOUDINARY_STORAGE_CONF['CLOUD_NAME'],
        api_key=CLOUDINARY_STORAGE_CONF['API_KEY'],
        api_secret=CLOUDINARY_STORAGE_CONF['API_SECRET'],
        secure=True
    )
    
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    print(f"☁️ [Storage] Đang sử dụng Cloudinary: {CLOUDINARY_STORAGE_CONF['CLOUD_NAME']}")
else:
    # Chỉ dùng local khi KHÔNG CÓ key (Cảnh báo sẽ mất dữ liệu trên Railway)
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    print("⚠️ [Storage] Cảnh báo: Đang dùng Local Storage (Chưa nhập Cloudinary Key)")


# -----------------------------
# CORS + CSRF
# -----------------------------
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://doverx.vercel.app",
    "https://doverx-backend-production.up.railway.app",
]

CSRF_TRUSTED_ORIGINS = [
    "https://doverx-backend-production.up.railway.app",
    "https://doverx.vercel.app",
]

# -----------------------------
# REST FRAMEWORK
# -----------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
}

# -----------------------------
# CUSTOM USER MODEL
# -----------------------------
AUTH_USER_MODEL = "accounts.User"

# -----------------------------
# EMAIL CONFIG
# -----------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "trandacdaiviet@gmail.com"
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# -----------------------------
# JWT CONFIG
# -----------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SITE_URL = "https://doverx-backend-production.up.railway.app"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"