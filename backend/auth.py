"""
CoachAI authentication routes.

Endpoints (all return JSON):
  POST /api/auth/signup     {email, password, display_name?}    → 201, {user}
  POST /api/auth/login      {email, password}                   → 200, {user}
  POST /api/auth/logout                                         → 200, {ok}
  GET  /api/auth/me                                             → 200, {user|null}

Anonymous use is preserved everywhere else: the recommender, save-plan flow
gracefully degrades (save returns 401, generation works without auth).
"""

import re

from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required

from models import db, User


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name or user.email.split("@")[0],
    }


@auth_bp.post("/signup")
def signup():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip() or None

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with that email already exists."}), 409

    user = User(email=email, display_name=display_name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    return jsonify({"user": _user_payload(user)}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Email or password is incorrect."}), 401

    login_user(user)
    return jsonify({"user": _user_payload(user)})


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"ok": True})


@auth_bp.get("/me")
def me():
    if current_user.is_authenticated:
        return jsonify({"user": _user_payload(current_user)})
    return jsonify({"user": None})
