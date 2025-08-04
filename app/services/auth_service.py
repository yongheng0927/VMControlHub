# app/services/auth_services.py

from flask import request, jsonify
from app.models import User, db
from werkzeug.security import generate_password_hash
from flask_login import login_user as flask_login_user, logout_user
from sqlalchemy import func
import datetime


def register_user():
    """
    处理 POST /auth/register
    接收 JSON: {username, password}
    """
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({"error": "Username and password cannot be empty"}), 400

    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({"error": "Username already exists"}), 400


    hashed = generate_password_hash(password)
    current_time = datetime.datetime.now()

    new_user = User(
        username=username,
        password_hash=hashed,
        password_plain=None,
        must_change_password=False,
        password_last_changed=current_time
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Registration successful"}), 201

def login_user():
    """
    处理 POST /auth/login
    接收 JSON: {username, password}
    """
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({"error": "Username or password cannot be empty"}), 401

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Username or password is incorrect"})

    # 如果有 must_change_password = True，可返回特定字段提示前端跳转修改密码页
    # 这里示例：若必须修改密码，返回 code 提示
    if user.must_change_password:
        # 前端收到后可跳转到 /auth/change_password 或类似路由
        return jsonify({"error": "Must change password", "code": "MUST_CHANGE_PASSWORD"}), 403

    # 更新 last_login
    user.last_login = datetime.datetime.now()
    db.session.commit()

    # 登录用户，会话
    flask_login_user(user)
    return jsonify({"message": "Login successful"}), 200

def logout_current_user():
    """
    如果需要前端调用退出
    """
    logout_user()
    return jsonify({"message": "Logout successful"}), 200
