from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
import random
import datetime

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('user', 'User'),
    ]

    GENDER_CHOICES = [
        ('male', 'Nam'),
        ('female', 'Nữ'),
        ('other', 'Khác'),
    ]

    DOCTOR_TYPE_CHOICES = [
        ('doctor', 'Bác sĩ chính thức'),
        ('student', 'Sinh viên y khoa'),
        ('intern', 'Thực tập sinh'),
    ]

    # --- Thông tin tài khoản ---
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    is_verified = models.BooleanField(default=False)

    # --- Thông tin cá nhân ---
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    # --- Thông tin nghề nghiệp (chỉ áp dụng với bác sĩ) ---
    specialty = models.CharField(max_length=100, blank=True, null=True)
    workplace = models.CharField(max_length=150, blank=True, null=True)
    experience_years = models.PositiveIntegerField(blank=True, null=True)
    license_number = models.CharField(
        max_length=100, blank=True, null=True, help_text="Số chứng chỉ hành nghề"
    )
    doctor_type = models.CharField(
        max_length=50, choices=DOCTOR_TYPE_CHOICES, blank=True, null=True
    )

    # --- Xác minh OTP ---
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.email} ({self.role})"

    def generate_otp(self):
        self.otp_code = str(random.randint(100000, 999999))
        self.otp_expiry = timezone.now() + datetime.timedelta(minutes=10)
        self.save()

class UserStatus(models.Model):
    """Trạng thái online/offline của user"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='status')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Status"
        verbose_name_plural = "User Statuses"
    
    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else 'Offline'}"

class Friendship(models.Model):
    """
    Mối quan hệ bạn bè giữa 2 users
    
    Status:
    - pending: Đang chờ chấp nhận
    - accepted: Đã là bạn bè
    - rejected: Đã từ chối
    - blocked: Đã chặn
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('blocked', 'Blocked'),
    ]
    
    from_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_requests'
    )
    to_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='received_requests'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['from_user', 'to_user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.from_user.username} → {self.to_user.username} ({self.status})"
