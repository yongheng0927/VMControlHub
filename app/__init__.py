from dotenv import load_dotenv

load_dotenv()

import os
from flask import Flask, redirect, url_for, jsonify, request
from app.models import db, User
from app.config import MysqlConfig, SecretConfig
from flask_wtf import CSRFProtect
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
import time


login_manager = LoginManager()
csrf = CSRFProtect()

APP_START_TIME = time.time()

def get_real_ip(request):
    proxy_ip = request.headers.get('X-Real-IP')
    if proxy_ip:
        return proxy_ip.strip() 
    return request.remote_addr

from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.generic_crud import generic_crud_bp
from app.routes.control_vm import control_vm_bp
from app.routes.custom_fields import custom_fields_bp
from app.routes.health import health_bp
from app.routes.cache_stats import cache_stats_bp


def create_app():
    here = os.path.abspath(os.path.dirname(__file__))  
    static_path = os.path.normpath(os.path.join(here, '..', 'static'))
    template_path = os.path.join(here, 'templates')

    app = Flask(
        __name__,
        static_folder=static_path,
        static_url_path='/static',
        template_folder=template_path
    )
      
    app.config.from_object(MysqlConfig)
    app.config.from_object(SecretConfig)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # 登录配置
    login_manager.login_view = 'auth.login_page'
    login_manager.login_message = "Please login first to access this page"
    login_manager.login_message_category = "warning"

    # 注册蓝图
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(generic_crud_bp)
    app.register_blueprint(control_vm_bp)
    app.register_blueprint(custom_fields_bp)
    app.register_blueprint(cache_stats_bp)

    @app.route('/')
    def index():
        return redirect(url_for('dashboard.index'))

    # 自定义过滤器
    def omit_filter(d, *keys_to_omit):
        if not isinstance(d, dict):
            return d
        return {k: v for k, v in d.items() if k not in keys_to_omit}
    
    app.jinja_env.filters['omit'] = omit_filter

    return app

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except:
        return None