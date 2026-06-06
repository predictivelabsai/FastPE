"""Auth utilities: password hashing, token generation, email sending."""

from __future__ import annotations

import os
import secrets

import bcrypt

from utils.email import send_email

BASE_URL = os.getenv("SERVICE_URL", "https://pehero.chat")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def send_verification_email(email: str, token: str, name: str = ""):
    verify_url = f"{BASE_URL}/auth/verify/{token}"
    greeting = f"Hi {name}," if name else "Hi,"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#F5F5F5;font-family:'Inter',Arial,sans-serif;">
<div style="max-width:500px;margin:0 auto;padding:40px 20px;">
  <div style="background:#fff;border-radius:8px;padding:32px;border:1px solid #E5E7EB;">
    <h1 style="font-size:20px;font-weight:700;color:#1a3c6e;margin:0 0 16px;">
      Welcome to PE Hero
    </h1>
    <p style="color:#4B5563;font-size:14px;line-height:1.6;margin:0 0 16px;">
      {greeting}
    </p>
    <p style="color:#4B5563;font-size:14px;line-height:1.6;margin:0 0 24px;">
      Please verify your email address to activate your account.
    </p>
    <a href="{verify_url}"
       style="display:inline-block;background:#1a3c6e;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600;">
      Verify Email
    </a>
    <p style="color:#9CA3AF;font-size:12px;margin:24px 0 0;">
      If you didn't create an account, you can ignore this email.
    </p>
  </div>
</div>
</body></html>"""

    send_email(
        to=email,
        subject="Verify your PE Hero account",
        html_body=html,
        text_body=f"{greeting}\n\nVerify your email: {verify_url}\n\nIf you didn't create an account, ignore this.",
        tag="verify",
    )


def send_reset_email(email: str, token: str):
    reset_url = f"{BASE_URL}/auth/reset/{token}"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#F5F5F5;font-family:'Inter',Arial,sans-serif;">
<div style="max-width:500px;margin:0 auto;padding:40px 20px;">
  <div style="background:#fff;border-radius:8px;padding:32px;border:1px solid #E5E7EB;">
    <h1 style="font-size:20px;font-weight:700;color:#1a3c6e;margin:0 0 16px;">
      Reset your password
    </h1>
    <p style="color:#4B5563;font-size:14px;line-height:1.6;margin:0 0 24px;">
      Click the button below to set a new password. This link expires in 1 hour.
    </p>
    <a href="{reset_url}"
       style="display:inline-block;background:#1a3c6e;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600;">
      Reset Password
    </a>
    <p style="color:#9CA3AF;font-size:12px;margin:24px 0 0;">
      If you didn't request this, you can safely ignore this email.
    </p>
  </div>
</div>
</body></html>"""

    send_email(
        to=email,
        subject="Reset your PE Hero password",
        html_body=html,
        text_body=f"Reset your password: {reset_url}\n\nThis link expires in 1 hour.",
        tag="reset",
    )
