from app.models import db, ChangeLog
from flask import current_app
from flask_login import current_user
from datetime import datetime
import json

def to_dict(obj):
    """将 SQLAlchemy 模型对象或字典转换为可序列化为 JSON 的字典。"""
    if obj is None:
        return None
        
    # 处理基本类型
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
        
    # 处理字典
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            result[key] = to_dict(value)  # 递归处理字典的值
        return result
        
    # 处理列表和元组
    if isinstance(obj, (list, tuple)):
        return [to_dict(item) for item in obj]  # 递归处理列表中的每个元素
        
    # 处理日期时间
    if isinstance(obj, datetime):
        return obj.isoformat()
        
    # 处理SQLAlchemy模型对象
    try:
        # 尝试获取表的列
        if hasattr(obj, '__table__'):
            obj_dict = {}
            for c in obj.__table__.columns:
                value = getattr(obj, c.key)
                # 递归处理值
                obj_dict[c.key] = to_dict(value)
            return obj_dict
    except Exception as e:
        current_app.logger.error(f"Error converting SQLAlchemy object to dict: {str(e)}")
    
    # 尝试将对象转换为字符串
    try:
        return str(obj)
    except Exception:
        return {"error": "Error serializing object", "object_type": str(type(obj))}

def log_change(action, object_type, object_identifier, status='success', detail_obj=None):
    """
    根据项目中已有的 ChangeLog 模型记录变更。
    此函数只将日志条目添加到当前数据库会话中，并不执行提交。
    调用者需要负责在完成业务逻辑后统一提交会话。
    """
    try:
        username = current_user.username if current_user.is_authenticated else 'system'
        
        # 将复数模型名 (如 'vms') 转为单数 (如 'vm') 以匹配 ENUM
        if object_type.endswith('s'):
            object_type_singular = object_type[:-1]
        else:
            object_type_singular = object_type
        
        # 将 'imported' 操作映射到 'create'
        if action == 'imported':
            action = 'create'
        elif action == 'created':
            action = 'create'
        elif action == 'updated':
            action = 'update'
        elif action == 'deleted':
            action = 'delete'
        
        # 确保detail_obj是可序列化的
        serialized_detail = None
        if detail_obj is not None:
            try:
                serialized_detail = to_dict(detail_obj)
                # 验证序列化结果
                json.dumps(serialized_detail)  # 尝试转换为JSON字符串，验证是否可序列化
            except Exception as e:
                current_app.logger.error(f"Error serializing detail_obj: {str(e)}")
                serialized_detail = {"error": f"Error serializing: {str(e)}"}
        
        # 创建日志条目
        log_entry = ChangeLog(
            username=username,
            action=action,
            status=status,
            object_type=object_type_singular,
            object_identifier=str(object_identifier),
            detail=serialized_detail,
            time=datetime.now()
        )
        
        # 使用独立的会话来保存日志，确保即使主事务失败日志也能保存
        from sqlalchemy.orm import scoped_session, sessionmaker
        log_session = scoped_session(sessionmaker(bind=db.engine))
        log_session.add(log_entry)
        log_session.commit()
        
        # 在移除会话前获取需要的属性值
        log_entry_id = log_entry.id
        
        # 现在可以安全地移除会话
        log_session.remove()
        
        # 记录一条确认信息到应用日志
        current_app.logger.info(
            f"Change log created: ID={log_entry_id}, type={object_type_singular}, " +
            f"identifier={object_identifier}, action={action}, status={status}"
        )
        
    except Exception as e:
        # 在这里记录日志服务的内部错误，但不回滚会话，让调用者处理
        current_app.logger.error(f"Failed when preparing the changelog: {e}", exc_info=True)