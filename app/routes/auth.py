# /app/routes/auth.py 

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from flask_login import current_user, login_user as flask_login_user, logout_user
from app.models import User, db
from werkzeug.security import generate_password_hash
import datetime


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return render_template('auth.html')

@auth_bp.route('/login', methods=['POST'])
def login_post():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    current_app.logger.info(f"User attempts to log in: {username}")
    
    if not username or not password:
        current_app.logger.warning("Login failed: Missing username or password")
        return jsonify({"error": "Username or password cannot be empty"}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        current_app.logger.warning(f"Login failed: User {username} does not exist")
        return jsonify({"error": "Username or password is incorrect"}), 401
    
    # 详细日志记录
    current_app.logger.debug(f"User information: ID={user.id}, Role={user.role}, Must change password={user.must_change_password}")
    current_app.logger.debug(f"Password status: Plaintext exists={bool(user.temp_password)}, Hash exists={bool(user.password_hash)}")
    
    # 验证密码
    password_valid = user.check_password(password)
    
    if not password_valid:
        current_app.logger.warning(f"Login failed: User {username} password is incorrect")
        return jsonify({"error": "Username or password is incorrect"}), 401

    # 记录登录时间
    user.last_login = datetime.datetime.now()
    
    # 只检查 must_change_password 标志
    if user.must_change_password:
        current_app.logger.info(f"User {username} must change password, ID={user.id}")
        try:
            db.session.commit()
            return jsonify({
                "error": "must change password",
                "code": "MUST_CHANGE_PASSWORD",
                "userId": user.id
            }), 403
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update user login time failed: {str(e)}")
            return jsonify({"error": "system error, please try again"}), 500
    
    # 正常登录
    try:
        db.session.commit()
        flask_login_user(user)
        current_app.logger.info(f"User {username} login success")
        return jsonify({"message": "login success"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Login failed: User {username} login failed: {str(e)}")
        return jsonify({"error": "system error, please try again"}), 500

@auth_bp.route('/change_password', methods=['POST'])
def change_password():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    
    if not user_id or not old_password or not new_password:
        current_app.logger.warning("Change password failed: Missing necessary parameters")
        return jsonify({"error": "change password failed, please fill in all information"}), 400
    
    user = User.query.get(user_id)
    if not user:
        current_app.logger.warning(f"Change password failed: User ID {user_id} does not exist")
        return jsonify({"error": "user does not exist"}), 404
    
    # 验证旧密码
    if not user.check_password(old_password):
        current_app.logger.warning(f"Change password failed: User ID {user_id} old password is incorrect")
        return jsonify({"error": "old password is incorrect"}), 400
    
    # 验证新密码
    if len(new_password) < 6:
        current_app.logger.warning(f"Change password failed: User ID {user_id} new password length is less than 6 characters")
        return jsonify({"error": "new password length must be at least 6 characters"}), 400
    
    # 确保新密码与旧密码不同
    if new_password == old_password:
        current_app.logger.warning(f"Change password failed: User ID {user_id} new password must be different from old password")
        return jsonify({"error": "new password must be different from old password"}), 400
    
    # 更新密码
    try:
        user.set_password(new_password)
        user.must_change_password = False
        db.session.commit()
        current_app.logger.info(f"Change password success: User ID {user_id} password changed successfully")
        return jsonify({"message": "password changed successfully, please use new password to login"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to change the password: {str(e)}")
        return jsonify({"error": "system error, please try again"}), 500

@auth_bp.route('/register', methods=['GET'])
def register_page():
    if current_user.is_authenticated:
        current_app.logger.info(f"User {current_user.username} is already logged in")
        return redirect(url_for('dashboard.dashboard'))
    current_app.logger.debug("Rendering registration page")
    return render_template('auth.html')

@auth_bp.route('/register', methods=['POST'])
def register_post():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    current_app.logger.info(f"Registration request: {username}")
    
    if not username or not password:
        current_app.logger.warning("Registration failed: Missing username or password")
        return jsonify({"error": "username and password cannot be empty"}), 400

    existing = User.query.filter_by(username=username).first()
    if existing:
        current_app.logger.warning(f"Registration failed: Username {username} already exists")
        return jsonify({"error": "username already exists"}), 400

    current_time = datetime.datetime.now()

    try:
        # 创建新用户
        new_user = User(
            username=username,
            password_hash=generate_password_hash(password),
            must_change_password=False,
            created_at=current_time,
            role='operator'  # 默认角色
        )
        db.session.add(new_user)
        db.session.commit()
        
        current_app.logger.info(f"Registration success: User {username} registered successfully, ID={new_user.id}")
        current_app.logger.info(f"Registration time: {current_time}")
        return jsonify({"message": "registration success, please login"}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration failed: {str(e)}")
        return jsonify({"error": "registration failed, please try again"}), 500

@auth_bp.route('/logout', methods=['GET','POST'])
def logout_route():
    if current_user.is_authenticated:
        current_app.logger.info(f"User {current_user.username} logout")
        logout_user()
    return redirect(url_for('auth.login_page'))