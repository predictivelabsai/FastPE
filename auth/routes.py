"""Authentication routes: register, login, verify, forgot password, reset, Google OAuth."""

from __future__ import annotations

import logging
import os
import urllib.parse
from datetime import datetime, timedelta

import httpx

from fasthtml.common import (
    Html, Head, Body, Div, H2, H3, P, A, Button, Form, Input, Label, Script, NotStr, Meta, Link,
)
from starlette.responses import RedirectResponse, JSONResponse, Response

from app import rt
from auth.utils import (
    hash_password, verify_password, generate_token,
    send_verification_email, send_reset_email,
)
from db import connect, fetch_one
from utils.session import get_user_email, set_user_email, get_user_id, set_user_id, clear_user

log = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SERVICE_URL = os.getenv("SERVICE_URL", "https://pehero.chat")
GOOGLE_REDIRECT_URI = SERVICE_URL + "/auth/google/callback"


def _head(title: str):
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Link(rel="stylesheet", href="/static/app.css"),
    )


# ── Register ─────────────────────────────────────────────────────────

@rt("/auth/register", methods=["POST"])
async def auth_register(request):
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    name = (form.get("name") or "").strip()

    if not email or not password:
        return JSONResponse({"error": "Email and password are required"}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"error": "Password must be at least 6 characters"}, status_code=400)

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, password_hash FROM pehero.users WHERE email = %s",
            (email,),
        )
        existing = cur.fetchone()

        token = generate_token()
        pw_hash = hash_password(password)

        if existing:
            if existing[1]:
                return JSONResponse({"error": "An account with this email already exists"}, status_code=409)
            cur.execute("""
                UPDATE pehero.users
                SET password_hash = %s, name = %s, verify_token = %s, is_verified = FALSE
                WHERE email = %s
            """, (pw_hash, name, token, email))
        else:
            cur.execute("""
                INSERT INTO pehero.users (email, password_hash, name, verify_token, is_verified)
                VALUES (%s, %s, %s, %s, FALSE)
            """, (email, pw_hash, name, token))
        conn.commit()

    send_verification_email(email, token, name)
    return JSONResponse({"ok": True, "message": "Check your email to verify your account"})


# ── Verify email ─────────────────────────────────────────────────────

@rt("/auth/verify/{token}")
def auth_verify(token: str, sess):
    row = fetch_one(
        "SELECT id, email FROM pehero.users WHERE verify_token = %s",
        (token,),
    )
    if not row:
        return Html(_head("Verification"), Body(
            Div(H2("Invalid or expired link"), P("Please register again."),
                A("Back to app", href="/app"),
                style="max-width:400px;margin:80px auto;text-align:center;font-family:sans-serif"),
        ))

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE pehero.users
            SET is_verified = TRUE, verify_token = NULL
            WHERE id = %s
        """, (row["id"],))
        conn.commit()

    set_user_email(sess, row["email"])
    set_user_id(sess, row["id"])
    return RedirectResponse("/app", status_code=303)


# ── Login ────────────────────────────────────────────────────────────

@rt("/auth/login", methods=["POST"])
async def auth_login(request, sess):
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""

    if not email or not password:
        return JSONResponse({"error": "Email and password are required"}, status_code=400)

    row = fetch_one(
        "SELECT id, email, password_hash, is_verified, name FROM pehero.users WHERE email = %s",
        (email,),
    )

    if not row:
        return JSONResponse({"error": "Invalid email or password"}, status_code=401)

    if not row["password_hash"]:
        return JSONResponse({"error": "no_password", "message": "Please set a password for your account"}, status_code=401)

    if not verify_password(password, row["password_hash"]):
        return JSONResponse({"error": "Invalid email or password"}, status_code=401)

    set_user_email(sess, row["email"])
    set_user_id(sess, row["id"])
    return JSONResponse({"ok": True, "email": row["email"], "name": row["name"] or ""})


# ── Forgot password ──────────────────────────────────────────────────

@rt("/auth/forgot", methods=["POST"])
async def auth_forgot(request):
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"error": "Email is required"}, status_code=400)

    row = fetch_one("SELECT id FROM pehero.users WHERE email = %s", (email,))
    if row:
        token = generate_token()
        expires = datetime.utcnow() + timedelta(hours=1)
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE pehero.users
                SET reset_token = %s, reset_token_expires = %s
                WHERE id = %s
            """, (token, expires, row["id"]))
            conn.commit()
        send_reset_email(email, token)

    return JSONResponse({"ok": True, "message": "If an account exists, a reset link has been sent"})


# ── Reset password ───────────────────────────────────────────────────

@rt("/auth/reset/{token}")
def auth_reset_page(token: str):
    row = fetch_one(
        "SELECT id FROM pehero.users WHERE reset_token = %s AND reset_token_expires > NOW()",
        (token,),
    )
    if not row:
        return Html(_head("Reset Password"), Body(
            Div(H2("Invalid or expired link"), P("Please request a new reset link."),
                A("Back to app", href="/app"),
                style="max-width:400px;margin:80px auto;text-align:center;font-family:sans-serif"),
        ))

    return Html(_head("Reset Password"), Body(
        Div(
            H2("Set new password", style="font-size:1.2rem;font-weight:700;margin-bottom:16px"),
            Form(
                Input(type="password", name="password", placeholder="New password (min 6 chars)",
                      style="width:100%;padding:8px 12px;border:1px solid #E5E7EB;border-radius:6px;font-size:14px;margin-bottom:12px", required=True),
                Input(type="password", name="password_confirm", placeholder="Confirm password",
                      style="width:100%;padding:8px 12px;border:1px solid #E5E7EB;border-radius:6px;font-size:14px;margin-bottom:16px", required=True),
                Button("Reset Password", type="submit",
                       style="width:100%;padding:10px;background:#1a3c6e;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer;font-weight:600"),
                method="POST",
                action=f"/auth/reset/{token}/submit",
            ),
            style="max-width:360px;margin:80px auto;padding:24px;background:#fff;border-radius:8px;border:1px solid #E5E7EB;font-family:sans-serif",
        ),
    ))


@rt("/auth/reset/{token}/submit", methods=["POST"])
async def auth_reset_submit(token: str, request, sess):
    form = await request.form()
    password = form.get("password") or ""
    password_confirm = form.get("password_confirm") or ""

    if len(password) < 6 or password != password_confirm:
        return RedirectResponse(f"/auth/reset/{token}", status_code=303)

    row = fetch_one(
        "SELECT id, email FROM pehero.users WHERE reset_token = %s AND reset_token_expires > NOW()",
        (token,),
    )
    if not row:
        return RedirectResponse("/app", status_code=303)

    pw_hash = hash_password(password)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE pehero.users
            SET password_hash = %s, reset_token = NULL, reset_token_expires = NULL, is_verified = TRUE
            WHERE id = %s
        """, (pw_hash, row["id"]))
        conn.commit()

    set_user_email(sess, row["email"])
    set_user_id(sess, row["id"])
    return RedirectResponse("/app", status_code=303)


# ── Set password (for OAuth users) ───────────────────────────────────

@rt("/auth/set-password", methods=["POST"])
async def auth_set_password(request, sess):
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""

    if not email or len(password) < 6:
        return JSONResponse({"error": "Email and password (min 6 chars) required"}, status_code=400)

    row = fetch_one(
        "SELECT id FROM pehero.users WHERE email = %s AND password_hash IS NULL",
        (email,),
    )
    if not row:
        return JSONResponse({"error": "Account not found or already has password"}, status_code=404)

    pw_hash = hash_password(password)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE pehero.users SET password_hash = %s, is_verified = TRUE
            WHERE id = %s
        """, (pw_hash, row["id"]))
        conn.commit()

    set_user_email(sess, email)
    set_user_id(sess, row["id"])
    return JSONResponse({"ok": True, "email": email})


# ── Logout ───────────────────────────────────────────────────────────

@rt("/auth/logout", methods=["POST"])
def auth_logout(sess):
    clear_user(sess)
    return JSONResponse({"ok": True})


# ── Google OAuth ─────────────────────────────────────────────────────

@rt("/auth/google")
def auth_google_redirect(sess):
    if not GOOGLE_CLIENT_ID:
        return JSONResponse({"error": "Google OAuth not configured"}, status_code=500)

    state = generate_token()
    sess["oauth_state"] = state

    params = urllib.parse.urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}", status_code=302)


@rt("/auth/google/callback")
def auth_google_callback(request, sess):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        log.warning(f"Google OAuth error: {error}")
        return RedirectResponse("/app", status_code=303)

    if not code or state != sess.get("oauth_state"):
        log.warning("Google OAuth: invalid state or missing code")
        return RedirectResponse("/app", status_code=303)

    sess.pop("oauth_state", None)

    token_resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        log.error(f"Google token exchange failed: {token_resp.text}")
        return RedirectResponse("/app", status_code=303)

    tokens = token_resp.json()
    access_token = tokens.get("access_token")

    userinfo_resp = httpx.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if userinfo_resp.status_code != 200:
        log.error(f"Google userinfo failed: {userinfo_resp.text}")
        return RedirectResponse("/app", status_code=303)

    userinfo = userinfo_resp.json()
    email = userinfo.get("email", "").lower().strip()
    name = userinfo.get("name", "")

    if not email:
        return RedirectResponse("/app", status_code=303)

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, email, name FROM pehero.users WHERE email = %s", (email,))
        row = cur.fetchone()

        if row:
            uid = row[0]
            if not row[2] and name:
                cur.execute("UPDATE pehero.users SET name = %s WHERE id = %s", (name, uid))
                conn.commit()
        else:
            cur.execute("""
                INSERT INTO pehero.users (email, name, is_verified)
                VALUES (%s, %s, TRUE)
                RETURNING id
            """, (email, name))
            uid = cur.fetchone()[0]
            conn.commit()

    set_user_email(sess, email)
    set_user_id(sess, uid)
    return RedirectResponse("/app", status_code=303)
