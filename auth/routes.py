"""Authentication routes: register, login, verify, forgot password, reset, Google OAuth, profile."""

from __future__ import annotations

import json as _json
import logging
import os
import urllib.parse
from datetime import datetime, timedelta

import httpx

from fasthtml.common import (
    Html, Head, Body, Div, H2, H3, P, A, Button, Form, Input, Label,
    Script, NotStr, Meta, Link, Style, Span,
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


GOOGLE_SVG = '<svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg"><path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"/><path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/><path d="M3.964 10.71c-.18-.54-.282-1.117-.282-1.71s.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9s.348 1.452.957 2.042l3.007-2.332z" fill="#FBBC05"/><path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/></svg>'

_INPUT_CLS = "w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-[#1B4D3E] focus:outline-none"
_BTN_CLS = "w-full bg-[#1B4D3E] text-white py-2.5 rounded-lg font-semibold text-sm hover:bg-[#163f33] transition-colors"
_GOOGLE_BTN_CLS = "flex items-center justify-center gap-2 w-full border border-gray-200 bg-white text-gray-700 py-2.5 rounded-lg font-medium text-sm hover:bg-gray-50 hover:border-gray-300 transition-colors no-underline"


def _auth_layout(title: str, card_parts: list):
    from fasthtml.common import Title, Main, Script
    return (
        Title(f"{title} — PEHero"),
        Script(src="https://cdn.tailwindcss.com"),
        Main(
            Div(
                Div(
                    Div("◆", cls="w-14 h-14 rounded-xl bg-gradient-to-br from-[#1B4D3E] to-[#2d7a5f] text-white flex items-center justify-center text-xl font-extrabold mx-auto"),
                    P("PEHero", cls="text-xl font-bold text-[#1B4D3E] mt-2"),
                    P("Your Private Equity AI Agent Squad", cls="text-xs text-gray-500"),
                    cls="text-center mb-6",
                ),
                Div(*card_parts, cls="w-full max-w-sm bg-white border border-gray-200 rounded-xl p-8 shadow-lg"),
                P("PE Hero Ltd", cls="text-xs text-gray-400 mt-6"),
                cls="flex flex-col items-center justify-center min-h-screen",
            ),
            cls="bg-gray-50",
        ),
    )


def _divider():
    return Div(
        Div(cls="flex-1 h-px bg-gray-200"),
        Span("or", cls="px-3 text-xs text-gray-400"),
        Div(cls="flex-1 h-px bg-gray-200"),
        cls="flex items-center my-4",
    )


def _error_msg(msg: str):
    return Div(msg, cls="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg text-center") if msg else ""


def _success_msg(msg: str):
    return Div(msg, cls="text-sm text-green-600 bg-green-50 px-3 py-2 rounded-lg text-center") if msg else ""


@rt("/signin")
async def signin_page(request, sess):
    if get_user_email(sess):
        return RedirectResponse("/app", status_code=303)

    error = ""
    if request.method == "POST":
        form = await request.form()
        email = (form.get("email") or "").strip().lower()
        password = form.get("password") or ""
        if not email or not password:
            error = "Email and password are required"
        else:
            user = fetch_one("SELECT id, email, password_hash FROM pehero.users WHERE email = %s", [email])
            if not user or not user.get("password_hash"):
                error = "Invalid email or password"
            else:
                if not verify_password(password, user["password_hash"]):
                    error = "Invalid email or password"
                else:
                    set_user_email(sess, user["email"])
                    set_user_id(sess, user["id"])
                    return RedirectResponse("/app", status_code=303)

    parts = [H2("Sign In", cls="text-xl font-bold text-center mb-4")]
    if error:
        parts.append(_error_msg(error))
    if GOOGLE_CLIENT_ID:
        parts.append(A(NotStr(GOOGLE_SVG), "Continue with Google", href="/auth/google", cls=_GOOGLE_BTN_CLS))
        parts.append(_divider())
    parts.append(
        Form(
            Input(type="email", name="email", placeholder="Email", required=True, autofocus=True, cls=_INPUT_CLS),
            Input(type="password", name="password", placeholder="Password", required=True, cls=_INPUT_CLS + " mt-3"),
            Div(A("Forgot password?", href="/forgot", cls="text-[#1B4D3E] hover:underline"), cls="text-right text-xs mt-1 mb-4"),
            Button("Sign In", type="submit", cls=_BTN_CLS),
            method="post", action="/signin", cls="flex flex-col gap-3",
        )
    )
    parts.append(Div("Don't have an account? ", A("Sign up", href="/register", cls="text-[#1B4D3E] hover:underline"), cls="text-center text-sm text-gray-500 mt-4"))
    return _auth_layout("Sign In", parts)


@rt("/register")
async def register_page(request, sess):
    if get_user_email(sess):
        return RedirectResponse("/app", status_code=303)

    error = ""
    success = ""
    if request.method == "POST":
        form = await request.form()
        name = (form.get("name") or "").strip()
        email = (form.get("email") or "").strip().lower()
        password = form.get("password") or ""
        if not email or not password:
            error = "Email and password are required"
        elif len(password) < 6:
            error = "Password must be at least 6 characters"
        else:
            existing = fetch_one("SELECT id FROM pehero.users WHERE email = %s", [email])
            if existing:
                error = "An account with this email already exists"
            else:
                token = generate_token()
                with connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO pehero.users (email, password_hash, name, verify_token, is_verified) "
                            "VALUES (%s, %s, %s, %s, FALSE) RETURNING id",
                            [email, hash_password(password), name or None, token],
                        )
                        conn.commit()
                try:
                    send_verification_email(email, token)
                    success = "Account created! Check your email to verify."
                except Exception:
                    log.exception("Failed to send verification email")
                    success = "Account created! (Email verification pending)"

    parts = [H2("Create Account", cls="text-xl font-bold text-center mb-4")]
    if error:
        parts.append(_error_msg(error))
    if success:
        parts.append(_success_msg(success))
    if GOOGLE_CLIENT_ID:
        parts.append(A(NotStr(GOOGLE_SVG), "Sign up with Google", href="/auth/google", cls=_GOOGLE_BTN_CLS))
        parts.append(_divider())
    parts.append(
        Form(
            Input(type="text", name="name", placeholder="Name (optional)", cls=_INPUT_CLS),
            Input(type="email", name="email", placeholder="Email", required=True, cls=_INPUT_CLS + " mt-3"),
            Input(type="password", name="password", placeholder="Password (min 6 characters)", required=True, minlength="6", cls=_INPUT_CLS + " mt-3"),
            Button("Create Account", type="submit", cls=_BTN_CLS + " mt-2"),
            method="post", action="/register", cls="flex flex-col gap-3",
        )
    )
    parts.append(Div("Already have an account? ", A("Sign in", href="/signin", cls="text-[#1B4D3E] hover:underline"), cls="text-center text-sm text-gray-500 mt-4"))
    return _auth_layout("Register", parts)


@rt("/forgot")
async def forgot_page(request, sess):
    if get_user_email(sess):
        return RedirectResponse("/app", status_code=303)

    error = ""
    success = ""
    if request.method == "POST":
        form = await request.form()
        email = (form.get("email") or "").strip().lower()
        if not email:
            error = "Please enter your email"
        else:
            user = fetch_one("SELECT id, email FROM pehero.users WHERE email = %s", [email])
            if user:
                token = generate_token()
                with connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE pehero.users SET reset_token = %s, reset_token_expires = NOW() + INTERVAL '1 hour' WHERE id = %s",
                            [token, user["id"]],
                        )
                        conn.commit()
                try:
                    send_reset_email(email, token)
                except Exception:
                    log.exception("Failed to send reset email")
            success = "If an account exists, a reset link has been sent"

    parts = [H2("Forgot Password", cls="text-xl font-bold text-center mb-4")]
    if error:
        parts.append(_error_msg(error))
    if success:
        parts.append(_success_msg(success))
    parts.append(P("Enter your email and we'll send you a reset link.", cls="text-sm text-gray-500 text-center mb-3"))
    parts.append(
        Form(
            Input(type="email", name="email", placeholder="Email", required=True, autofocus=True, cls=_INPUT_CLS),
            Button("Send Reset Link", type="submit", cls=_BTN_CLS + " mt-2"),
            method="post", action="/forgot", cls="flex flex-col gap-3",
        )
    )
    parts.append(Div(A("Back to sign in", href="/signin", cls="text-[#1B4D3E] hover:underline"), cls="text-center text-sm mt-4"))
    return _auth_layout("Forgot Password", parts)


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


# ── Unsubscribe (token-based, no login required) ───────────────────

@rt("/auth/unsubscribe/{token}")
def auth_unsubscribe(token: str):
    row = fetch_one(
        "SELECT user_id FROM pehero.user_preferences WHERE unsubscribe_token = %s",
        (token,),
    )
    if row:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE pehero.user_preferences SET notify_new_deals = FALSE WHERE user_id = %s",
                (row["user_id"],),
            )
            conn.commit()

    return Html(_head("Unsubscribed"), Body(
        Div(
            H2("Unsubscribed"),
            P("You've been unsubscribed from daily deal emails."),
            P("You can re-enable notifications anytime from your ",
              A("profile settings", href="/app/profile"), "."),
            A("Back to PEHero", href="/app"),
            style="max-width:400px;margin:80px auto;text-align:center;font-family:sans-serif",
        ),
    ))


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


# ── Profile & Preferences ──────────────────────────────────────────

SECTORS = [
    "Technology", "Healthcare", "Financial Services", "Consumer",
    "Industrials", "Energy", "Real Estate", "Infrastructure", "TMT",
]
DEAL_TYPES = [
    "Buyout", "Growth Equity", "Venture", "Secondaries",
    "Distressed", "Mezzanine", "Co-Investment",
]
GEOGRAPHIES = [
    "Baltics", "Nordics", "CEE", "Western Europe",
    "UK", "US", "Global",
]
STAGES = [
    ("", "Any"), ("seed", "Seed"), ("series_a", "Series A"),
    ("series_b", "Series B"), ("growth", "Growth"),
    ("late_stage", "Late Stage"), ("pre_ipo", "Pre-IPO"),
]
PROFILE_CURRENCIES = [("EUR", "EUR — Euro"), ("GBP", "GBP — Pound"), ("USD", "USD — Dollar")]
PROFILE_LANGUAGES = [
    ("en", "English"), ("de", "Deutsch"), ("fr", "Francais"),
    ("et", "Eesti"), ("lv", "Latviesu"), ("lt", "Lietuviu"),
    ("ro", "Romana"), ("pl", "Polski"),
]


def _checkbox_group(name, options, selected):
    items = []
    for opt in options:
        checked = "checked" if opt in selected else ""
        items.append(NotStr(
            f'<label class="cb-pill"><input type="checkbox" name="{name}" value="{opt}" {checked}>'
            f'<span>{opt}</span></label>'
        ))
    return Div(*items, cls="cb-group")


def _select(name, options, selected, cls="prf-input"):
    opts_html = "".join(
        f'<option value="{v}"{" selected" if v == selected else ""}>{label}</option>'
        for v, label in options
    )
    return NotStr(f'<select name="{name}" class="{cls}">{opts_html}</select>')


def _toggle(name, label_text, checked):
    chk = "checked" if checked else ""
    return Div(NotStr(
        f'<label class="toggle-row"><input type="checkbox" name="{name}" value="1" {chk}>'
        f'<span class="toggle-label">{label_text}</span></label>'
    ), cls="prf-toggle-wrap")


@rt("/app/profile")
def profile_page(sess):
    email = get_user_email(sess)
    if not email:
        return RedirectResponse("/app", status_code=303)

    uid = get_user_id(sess)
    user = fetch_one("SELECT name, email FROM pehero.users WHERE id = %s", (uid,))
    prefs = fetch_one("SELECT * FROM pehero.user_preferences WHERE user_id = %s", (uid,))

    name = user["name"] or "" if user else ""
    user_email = user["email"] if user else email

    p_phone = prefs["phone"] or "" if prefs else ""
    p_company = prefs["company"] or "" if prefs else ""
    p_role = prefs["role"] or "" if prefs else ""
    p_country = prefs["country"] or "" if prefs else ""
    p_city = prefs["city"] or "" if prefs else ""
    p_currency = prefs["currency"] or "EUR" if prefs else "EUR"
    p_lang = prefs["language"] or "en" if prefs else "en"

    p_dsmin = str(prefs["deal_size_min"] or "") if prefs else ""
    p_dsmax = str(prefs["deal_size_max"] or "") if prefs else ""
    p_rmin = str(prefs["revenue_min"] or "") if prefs else ""
    p_rmax = str(prefs["revenue_max"] or "") if prefs else ""
    p_emin = str(prefs["ebitda_min"] or "") if prefs else ""
    p_emax = str(prefs["ebitda_max"] or "") if prefs else ""

    p_sectors = _json.loads(prefs["preferred_sectors"]) if prefs and prefs["preferred_sectors"] else []
    p_deal_types = _json.loads(prefs["preferred_deal_types"]) if prefs and prefs["preferred_deal_types"] else []
    p_geos = _json.loads(prefs["preferred_geographies"]) if prefs and prefs["preferred_geographies"] else []
    p_stage = prefs["preferred_stage"] or "" if prefs else ""

    p_notify_new = prefs["notify_new_deals"] if prefs else True
    p_notify_updates = prefs["notify_deal_updates"] if prefs else True
    p_notify_digest = prefs["notify_weekly_digest"] if prefs else True

    inp = "prf-input"
    lbl = "prf-label"
    half = "prf-half"

    return Html(_head("Profile & Preferences"), Body(
        Div(
            A("< Back to chat", href="/app", cls="prf-back"),

            # ─── Account ────
            H2("Account", cls="prf-h2"),
            P("Your account details and password.", cls="prf-sub"),
            Form(
                Div(
                    Div(Label("Name", cls=lbl), Input(type="text", name="name", value=name, placeholder="Your name", cls=inp), cls=half),
                    Div(Label("Email", cls=lbl), Input(type="email", value=user_email, disabled=True, cls=f"{inp} prf-disabled"), cls=half),
                    cls="prf-row",
                ),
                Div(
                    Div(Label("Company", cls=lbl), Input(type="text", name="company", value=p_company, placeholder="e.g. Baltic Capital", cls=inp), cls=half),
                    Div(Label("Role / Title", cls=lbl), Input(type="text", name="role", value=p_role, placeholder="e.g. Investment Director", cls=inp), cls=half),
                    cls="prf-row",
                ),
                Div(
                    Div(Label("Phone", cls=lbl), Input(type="tel", name="phone", value=p_phone, placeholder="+370...", cls=inp), cls=half),
                    Div(Label("Country", cls=lbl), Input(type="text", name="country", value=p_country, placeholder="e.g. LT, EE", maxlength="5", cls=inp), cls=half),
                    Div(Label("City", cls=lbl), Input(type="text", name="city", value=p_city, placeholder="e.g. Vilnius", cls=inp), cls=half),
                    cls="prf-row prf-row-3",
                ),
                Div(
                    Div(Label("Currency", cls=lbl), _select("currency", PROFILE_CURRENCIES, p_currency), cls=half),
                    Div(Label("Language", cls=lbl), _select("language", PROFILE_LANGUAGES, p_lang), cls=half),
                    cls="prf-row",
                ),
                H3("Change Password", cls="prf-h3"),
                Div(
                    Div(Input(type="password", name="current_password", placeholder="Current password", cls=inp), cls=half),
                    Div(Input(type="password", name="new_password", placeholder="New password (min 6 chars)", cls=inp), cls=half),
                    cls="prf-row",
                ),
                Div(
                    Button("Save Account", type="submit", cls="prf-save-btn"),
                    Span(id="profile-msg", cls="prf-msg"),
                    cls="prf-btn-row",
                ),
                id="profile-form",
                onsubmit="return submitProfile(event)",
            ),

            # ─── Deal Preferences ────
            NotStr('<hr class="prf-hr">'),
            H2("Deal Preferences", cls="prf-h2"),
            P("Set your investment criteria — agents will tailor recommendations to your mandate.", cls="prf-sub"),
            Form(
                H3("Deal Size Range (EUR)", cls="prf-section-label"),
                Div(
                    Div(Label("Min", cls=lbl), Input(type="number", name="deal_size_min", value=p_dsmin, placeholder="e.g. 1000000", step="100000", cls=inp), cls=half),
                    Div(Label("Max", cls=lbl), Input(type="number", name="deal_size_max", value=p_dsmax, placeholder="e.g. 50000000", step="100000", cls=inp), cls=half),
                    cls="prf-row",
                ),

                H3("Preferred Sectors", cls="prf-section-label"),
                _checkbox_group("preferred_sectors", SECTORS, p_sectors),

                H3("Deal Types", cls="prf-section-label"),
                _checkbox_group("preferred_deal_types", DEAL_TYPES, p_deal_types),

                H3("Geographies", cls="prf-section-label"),
                _checkbox_group("preferred_geographies", GEOGRAPHIES, p_geos),

                H3("Financial Criteria", cls="prf-section-label"),
                Div(
                    Div(Label("Stage", cls=lbl), _select("preferred_stage", STAGES, p_stage), cls=half),
                    cls="prf-row",
                ),
                Div(
                    Div(Label("Revenue Min (EUR)", cls=lbl), Input(type="number", name="revenue_min", value=p_rmin, placeholder="e.g. 500000", step="100000", cls=inp), cls=half),
                    Div(Label("Revenue Max (EUR)", cls=lbl), Input(type="number", name="revenue_max", value=p_rmax, placeholder="e.g. 20000000", step="100000", cls=inp), cls=half),
                    cls="prf-row",
                ),
                Div(
                    Div(Label("EBITDA Min (EUR)", cls=lbl), Input(type="number", name="ebitda_min", value=p_emin, placeholder="e.g. 100000", step="50000", cls=inp), cls=half),
                    Div(Label("EBITDA Max (EUR)", cls=lbl), Input(type="number", name="ebitda_max", value=p_emax, placeholder="e.g. 5000000", step="50000", cls=inp), cls=half),
                    cls="prf-row",
                ),
                Div(
                    Button("Save Preferences", type="submit", cls="prf-save-btn"),
                    Span(id="prefs-msg", cls="prf-msg"),
                    cls="prf-btn-row",
                ),
                id="prefs-form",
                onsubmit="return submitPrefs(event)",
            ),

            # ─── Notifications ────
            NotStr('<hr class="prf-hr">'),
            H2("Notifications", cls="prf-h2"),
            P("Choose what emails you'd like to receive.", cls="prf-sub"),
            Form(
                _toggle("notify_new_deals", "New deals matching my investment criteria", p_notify_new),
                _toggle("notify_deal_updates", "Deal status changes in my pipeline", p_notify_updates),
                _toggle("notify_weekly_digest", "Weekly market digest", p_notify_digest),
                Div(
                    Button("Save Notifications", type="submit", cls="prf-save-btn"),
                    Span(id="notify-msg", cls="prf-msg"),
                    cls="prf-btn-row",
                ),
                id="notify-form",
                onsubmit="return submitNotify(event)",
            ),

            cls="prf-container",
        ),
        Style(NotStr("""
            .prf-container { max-width:640px; margin:32px auto 64px; padding:0 24px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }
            .prf-back { display:block; font-size:13px; color:#6B7280; text-decoration:none; margin-bottom:16px; }
            .prf-back:hover { color:#111; }
            .prf-h2 { font-size:1.25rem; font-weight:700; margin:0 0 4px; }
            .prf-sub { font-size:12px; color:#9CA3AF; margin:0 0 16px; }
            .prf-h3 { font-size:13px; font-weight:600; margin:12px 0 8px; }
            .prf-section-label { font-size:11px; font-weight:600; color:#6B7280; text-transform:uppercase; letter-spacing:.05em; margin:16px 0 8px; }
            .prf-label { display:block; font-size:11px; color:#6B7280; margin-bottom:4px; }
            .prf-input { width:100%; padding:7px 10px; border:1px solid #E5E7EB; border-radius:6px; font-size:13px; background:#fff; }
            .prf-input:focus { outline:none; border-color:#1a3c6e; }
            .prf-disabled { background:#F9FAFB; color:#9CA3AF; }
            .prf-row { display:flex; gap:12px; margin-bottom:12px; }
            .prf-row-3 .prf-half { flex:1; }
            .prf-half { flex:1; }
            .prf-hr { border:none; border-top:1px solid #F3F4F6; margin:32px 0; }
            .prf-save-btn { padding:8px 20px; background:#1a3c6e; color:#fff; border:none; border-radius:6px; font-size:13px; cursor:pointer; font-weight:600; }
            .prf-save-btn:hover { background:#15325a; }
            .prf-btn-row { display:flex; align-items:center; margin-top:8px; }
            .prf-msg { font-size:13px; margin-left:12px; }
            .cb-group { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }
            .cb-pill { display:inline-flex; align-items:center; gap:4px; padding:5px 12px; border:1px solid #e5e7eb; border-radius:20px; font-size:13px; cursor:pointer; transition:all .15s; user-select:none; }
            .cb-pill:has(input:checked) { background:#1a3c6e; color:#fff; border-color:#1a3c6e; }
            .cb-pill input { display:none; }
            .prf-toggle-wrap { margin-bottom:8px; }
            .toggle-row { display:flex; align-items:center; gap:8px; cursor:pointer; font-size:14px; }
            .toggle-row input { width:16px; height:16px; accent-color:#1a3c6e; }
            .toggle-label { color:#374151; }
            select.prf-input { appearance:auto; }
        """)),
        Script(NotStr("""
async function submitProfile(e) {
    e.preventDefault();
    var form = document.getElementById('profile-form');
    var resp = await fetch('/app/profile', { method:'POST', body: new FormData(form) });
    var data = await resp.json();
    var msg = document.getElementById('profile-msg');
    msg.style.color = data.ok ? '#16A34A' : '#DC2626';
    msg.textContent = data.ok ? 'Saved!' : (data.error || 'Error');
    setTimeout(function(){ msg.textContent = ''; }, 3000);
    return false;
}
async function submitPrefs(e) {
    e.preventDefault();
    var form = document.getElementById('prefs-form');
    var resp = await fetch('/api/user-preferences', { method:'POST', body: new FormData(form) });
    var data = await resp.json();
    var msg = document.getElementById('prefs-msg');
    msg.style.color = data.ok ? '#16A34A' : '#DC2626';
    msg.textContent = data.ok ? 'Preferences saved!' : (data.error || 'Error');
    setTimeout(function(){ msg.textContent = ''; }, 3000);
    return false;
}
async function submitNotify(e) {
    e.preventDefault();
    var form = document.getElementById('notify-form');
    var resp = await fetch('/api/user-preferences', { method:'POST', body: new FormData(form) });
    var data = await resp.json();
    var msg = document.getElementById('notify-msg');
    msg.style.color = data.ok ? '#16A34A' : '#DC2626';
    msg.textContent = data.ok ? 'Notification settings saved!' : (data.error || 'Error');
    setTimeout(function(){ msg.textContent = ''; }, 3000);
    return false;
}
""")),
        cls="prf-page",
        style="background:#fff; min-height:100vh;",
    ))


# ── Profile POST (account details) ─────────────────────────────────

@rt("/app/profile", methods=["POST"])
async def profile_update(request, sess):
    uid = get_user_id(sess)
    if not uid:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    form = await request.form()
    name = (form.get("name") or "").strip()
    phone = (form.get("phone") or "").strip()
    company = (form.get("company") or "").strip()
    role = (form.get("role") or "").strip()
    country = (form.get("country") or "").strip()
    city = (form.get("city") or "").strip()
    currency = form.get("currency") or "EUR"
    language = form.get("language") or "en"
    current_password = form.get("current_password") or ""
    new_password = form.get("new_password") or ""

    with connect() as conn, conn.cursor() as cur:
        if new_password:
            if len(new_password) < 6:
                return JSONResponse({"error": "New password must be at least 6 characters"}, status_code=400)
            cur.execute("SELECT password_hash FROM pehero.users WHERE id = %s", (uid,))
            row = cur.fetchone()
            if row and row[0]:
                if not verify_password(current_password, row[0]):
                    return JSONResponse({"error": "Current password is incorrect"}, status_code=400)
            cur.execute("UPDATE pehero.users SET name = %s, password_hash = %s WHERE id = %s",
                        (name, hash_password(new_password), uid))
        else:
            cur.execute("UPDATE pehero.users SET name = %s WHERE id = %s", (name, uid))

        cur.execute("""
            INSERT INTO pehero.user_preferences (user_id, phone, company, role, country, city, currency, language, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                phone = EXCLUDED.phone, company = EXCLUDED.company, role = EXCLUDED.role,
                country = EXCLUDED.country, city = EXCLUDED.city,
                currency = EXCLUDED.currency, language = EXCLUDED.language, updated_at = NOW()
        """, (uid, phone, company, role, country, city, currency, language))
        conn.commit()

    return JSONResponse({"ok": True})


# ── Deal preferences + notifications POST ──────────────────────────

@rt("/api/user-preferences", methods=["POST"])
async def update_user_prefs(request, sess):
    uid = get_user_id(sess)
    if not uid:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    form = await request.form()

    deal_size_min = form.get("deal_size_min") or None
    deal_size_max = form.get("deal_size_max") or None
    revenue_min = form.get("revenue_min") or None
    revenue_max = form.get("revenue_max") or None
    ebitda_min = form.get("ebitda_min") or None
    ebitda_max = form.get("ebitda_max") or None
    preferred_sectors = _json.dumps(form.getlist("preferred_sectors"))
    preferred_deal_types = _json.dumps(form.getlist("preferred_deal_types"))
    preferred_geographies = _json.dumps(form.getlist("preferred_geographies"))
    preferred_stage = form.get("preferred_stage") or None

    notify_new = "notify_new_deals" in form
    notify_updates = "notify_deal_updates" in form
    notify_digest = "notify_weekly_digest" in form

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO pehero.user_preferences (
                user_id, deal_size_min, deal_size_max, revenue_min, revenue_max,
                ebitda_min, ebitda_max, preferred_sectors, preferred_deal_types,
                preferred_geographies, preferred_stage,
                notify_new_deals, notify_deal_updates, notify_weekly_digest, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (user_id) DO UPDATE SET
                deal_size_min = EXCLUDED.deal_size_min, deal_size_max = EXCLUDED.deal_size_max,
                revenue_min = EXCLUDED.revenue_min, revenue_max = EXCLUDED.revenue_max,
                ebitda_min = EXCLUDED.ebitda_min, ebitda_max = EXCLUDED.ebitda_max,
                preferred_sectors = EXCLUDED.preferred_sectors,
                preferred_deal_types = EXCLUDED.preferred_deal_types,
                preferred_geographies = EXCLUDED.preferred_geographies,
                preferred_stage = EXCLUDED.preferred_stage,
                notify_new_deals = EXCLUDED.notify_new_deals,
                notify_deal_updates = EXCLUDED.notify_deal_updates,
                notify_weekly_digest = EXCLUDED.notify_weekly_digest,
                updated_at = NOW()
        """, (uid, deal_size_min, deal_size_max, revenue_min, revenue_max,
              ebitda_min, ebitda_max, preferred_sectors, preferred_deal_types,
              preferred_geographies, preferred_stage,
              notify_new, notify_updates, notify_digest))
        conn.commit()

    return JSONResponse({"ok": True})
