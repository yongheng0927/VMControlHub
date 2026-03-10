# app/__init__.py

from dotenv import load_dotenv

load_dotenv()

import os
from flask import Flask, redirect, url_for
from app.models import db, User
from app.config import MysqlConfig, SecretConfig
from flask_wtf import CSRFProtect
from flask_login import LoginManager
from flask_apscheduler import APScheduler


login_manager = LoginManager()
csrf = CSRFProtect()
scheduler = APScheduler()

# 蓝图
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.generic_crud import generic_crud_bp
from app.routes.control_vm import control_vm_bp
from app.routes.vm_sync import vm_sync_bp


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
    
    # 加载配置
    app.config.from_object(MysqlConfig)
    app.config.from_object(SecretConfig)

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # 初始化和启动定时任务
    scheduler.init_app(app)
    scheduler.start()
    
    # 添加定时任务：每天凌晨 00:05 同步一次 VM 状态
    from app.services.vm_status_sync_service import sync_vm_status_task
    scheduler.add_job(
        id='vm_status_sync',
        func=sync_vm_status_task,
        trigger='cron',  # 使用 cron 触发器
        hour=0,
        minute=5,
        replace_existing=True
    )
    app.logger.info("Scheduled VM status sync job added (daily at 00:05)")

    # 未登录访问需要登录的路由时，重定向到哪个 endpoint
    login_manager.login_view = 'auth.login_page'
    login_manager.login_message = "Please login first to access this page"
    login_manager.login_message_category = "warning"

    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(generic_crud_bp)
    app.register_blueprint(control_vm_bp)
    app.register_blueprint(vm_sync_bp)

    @app.route('/')
    def index():
        return redirect(url_for('dashboard.index'))

    # 自定义Jinja2过滤器
    def omit_filter(d, *keys_to_omit):
        if not isinstance(d, dict):
            return d
        return {k: v for k, v in d.items() if k not in keys_to_omit}
    
    app.jinja_env.filters['omit'] = omit_filter

    return app

# flask-login: user_loader 回调
@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except:
        return None