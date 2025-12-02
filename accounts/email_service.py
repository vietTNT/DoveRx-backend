import os
import requests

def send_otp_email_brevo(user):
    api_key = os.getenv("BREVO_API_KEY")
    url = "https://api.brevo.com/v3/smtp/email"

    payload = {
        "sender": {"name": "DoveRx", "email": "trandacdaiviet@gmail.com"},
        "to": [{"email": user.email}],
        "subject": "🔐 Mã xác nhận tài khoản DoveRx",
        "htmlContent": f"""
            <p>Xin chào {user.first_name or user.username},</p>
            <p>Mã xác nhận của bạn là:</p>
            <h2 style='color:#4A90E2'>{user.otp_code}</h2>
            <p>Có hiệu lực trong 10 phút.</p>
        """
    }

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        print("📧 Sent OTP via Brevo")
    except Exception as e:
        print("❌ Brevo send error:", e)
