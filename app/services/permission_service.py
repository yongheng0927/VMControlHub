# app/services/permission_service.py

from functools import wraps
from flask import jsonify, current_app
from flask_login import current_user


def role_required(*roles):
    """
    装饰器：限制只有特定角色可以访问
    
    用法:
        @role_required('admin', 'manager')
        def some_view():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Authentication required"}), 401
            
            if current_user.role not in roles:
                current_app.logger.warning(
                    f"Permission denied: User {current_user.username} "
                    f"(role: {current_user.role}) attempted to access "
                    f"{current_app.endpoint} requiring roles: {roles}"
                )
                return jsonify({
                    "error": "Permission denied",
                    "message": f"This action requires one of the following roles: {', '.join(roles)}"
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """装饰器：限制只有 admin 角色可以访问"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        
        if current_user.role != 'admin':
            current_app.logger.warning(
                f"Permission denied: User {current_user.username} "
                f"(role: {current_user.role}) attempted to access "
                f"{current_app.endpoint} requiring role: admin"
            )
            return jsonify({
                "error": "Permission denied",
                "message": "This action requires admin role"
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function


def manager_or_admin_required(f):
    """装饰器：限制只有 manager 或 admin 角色可以访问"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        
        if current_user.role not in ['manager', 'admin']:
            current_app.logger.warning(
                f"Permission denied: User {current_user.username} "
                f"(role: {current_user.role}) attempted to access "
                f"{current_app.endpoint} requiring roles: manager, admin"
            )
            return jsonify({
                "error": "Permission denied",
                "message": "This action requires manager or admin role"
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function


def can_edit_model(model_name):
    """
    装饰器：根据模型名称和用户角色检查编辑权限
    
    权限规则:
    - admin: 可以编辑所有模型
    - manager: 可以编辑除了 users 之外的所有模型
    - operator: 不能编辑任何模型
    
    用法:
        @can_edit_model('vms')
        def edit_vm():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Authentication required"}), 401
            
            if current_user.role == 'admin':
                return f(*args, **kwargs)
            
            if current_user.role == 'manager' and model_name != 'users':
                return f(*args, **kwargs)
            
            current_app.logger.warning(
                f"Permission denied: User {current_user.username} "
                f"(role: {current_user.role}) attempted to edit {model_name}"
            )
            return jsonify({
                "error": "Permission denied",
                "message": f"You don't have permission to edit {model_name}"
            }), 403
        
        return decorated_function
    return decorator


def can_delete_model(model_name):
    """
    装饰器：根据模型名称和用户角色检查删除权限
    
    权限规则:
    - admin: 可以删除所有模型
    - manager: 不能删除任何模型
    - operator: 不能删除任何模型
    
    用法:
        @can_delete_model('vms')
        def delete_vm():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Authentication required"}), 401
            
            if current_user.role == 'admin':
                return f(*args, **kwargs)
            
            current_app.logger.warning(
                f"Permission denied: User {current_user.username} "
                f"(role: {current_user.role}) attempted to delete {model_name}"
            )
            return jsonify({
                "error": "Permission denied",
                "message": f"You don't have permission to delete {model_name}"
            }), 403
        
        return decorated_function
    return decorator


def can_create_model(model_name):
    """
    装饰器：根据模型名称和用户角色检查创建权限
    
    权限规则:
    - admin: 可以创建所有模型
    - manager: 可以创建除了 users 之外的所有模型
    - operator: 不能创建任何模型
    
    用法:
        @can_create_model('vms')
        def create_vm():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Authentication required"}), 401
            
            if current_user.role == 'admin':
                return f(*args, **kwargs)
            
            if current_user.role == 'manager' and model_name != 'users':
                return f(*args, **kwargs)
            
            current_app.logger.warning(
                f"Permission denied: User {current_user.username} "
                f"(role: {current_user.role}) attempted to create {model_name}"
            )
            return jsonify({
                "error": "Permission denied",
                "message": f"You don't have permission to create {model_name}"
            }), 403
        
        return decorated_function
    return decorator
