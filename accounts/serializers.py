from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from urllib.parse import urlparse, urlunparse, quote
from .models import Friendship


User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["username", "password", "email", "first_name", "last_name"]

    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data["username"],
            email=validated_data["email"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", "")
        )
        user.set_password(validated_data["password"])
        user.save()
        return user





class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id","email","username","first_name","last_name","role",
            "avatar","bio","gender","age","phone","address",
            "specialty","workplace","experience_years","license_number","doctor_type",
        ]
        read_only_fields = ["id","email","role"]

    # map từ chữ Việt → key trong DB
    def validate_gender(self, value):
        mapping = {"Nam":"male","Nữ":"female","Khác":"other","":None,None:None}
        return mapping.get(value, value)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")

        # trả giới tính tiếng Việt về FE
        mapping = {"male":"Nam","female":"Nữ","other":"Khác"}
        data["gender"] = mapping.get(instance.gender, "") if instance.gender else ""

        # xử lý avatar URL
        if instance.avatar and hasattr(instance.avatar, "url"):
            data["avatar"] = instance.avatar.url   # Cloudinary đã trả HTTPS
        else:
            data["avatar"] = None

        # tên hiển thị tiện dụng
        full_name = f"{(instance.first_name or '').strip()} {(instance.last_name or '').strip()}".strip()
        data["name"] = full_name or instance.username or (instance.email.split("@")[0] if instance.email else "")
        return data

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        refresh = self.get_token(self.user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        data["user"] = UserSerializer(self.user).data
        return data

class FriendshipSerializer(serializers.ModelSerializer):
    from_user = UserSerializer(read_only=True)
    to_user = UserSerializer(read_only=True)
    
    class Meta:
        model = Friendship
        fields = ['id', 'from_user', 'to_user', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
