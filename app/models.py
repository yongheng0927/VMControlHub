from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import ENUM, JSON
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='用户ID,自增主键')
    username = db.Column(db.String(100), unique=True, nullable=False, comment='登录用户名,全局唯一')
    password_hash = db.Column(db.String(255), nullable=True, comment='密码哈希值,存储加密后的密码')
    temp_password = db.Column(db.String(255), nullable=True, comment='临时明文密码(仅用于首次登录)')
    role = db.Column(ENUM('admin', 'manager', 'operator', name='role_enum'), nullable=False, server_default='operator', comment='用户角色,控制权限范围')
    must_change_password = db.Column(db.Integer, nullable=False, server_default='1', comment='密码重置标志,首次登录强制修改密码')
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='用户创建时间')
    last_login = db.Column(db.DateTime, nullable=True, comment='最后登录时间')
    password_last_changed = db.Column(db.DateTime, nullable=True, comment='最后密码修改时间')
    table_set = db.Column(JSON, nullable=True, comment='用户浏览器表格样式')

    def check_password(self, password):
        """验证密码(支持明文和哈希两种方式)"""
        if self.must_change_password and not self.password_hash and self.temp_password:
            return password == self.temp_password
        elif self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False

    def set_password(self, new_password):
        """设置新密码(将明文转为哈希,并清空临时明文密码)"""
        self.password_hash = generate_password_hash(new_password)
        self.temp_password = None
        self.must_change_password = False
        self.password_last_changed = datetime.now()

    def __repr__(self):
        return f"<User {self.username}>"

class Host(db.Model):
    __tablename__ = 'hosts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主机id,自增主键')
    host_info = db.Column(db.String(255), unique=True, nullable=False, comment='主机标识,格式为"ipv4_hostname"')
    virtualization_type = db.Column(ENUM('kvm', 'pve', 'other', name='virtualization_enum'), nullable=False, comment='虚拟化类型,决定管理方式')
    department = db.Column(db.String(100), nullable=False, comment='所属部门,用于权限和统计')
    status = db.Column(ENUM('running', 'stopped', 'unknown', name='host_status_enum'), nullable=False, server_default='unknown', comment='主机状态')
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间,自动维护')
    vm_count = db.Column(db.Integer, nullable=False, server_default='0', comment='宿主机关联的VM数量')

    # 关系：一个主机包含多个VM
    vms = db.relationship('VM', back_populates='host', cascade='all, delete-orphan')

    def __getitem__(self, key):
        """支持通过字典访问方式获取自定义字段值（重构后适配新表结构）"""
        from app.models import CustomField, CustomFieldValue
        
        # 先尝试获取原生字段
        try:
            return getattr(self, key)
        except AttributeError:
            pass
        
        # 查找自定义字段 - 先尝试用 id 查找，再尝试用 field_name 查找
        field = None
        try:
            field_id = int(key)
            field = CustomField.query.filter_by(
                resource_type='host',
                id=field_id
            ).first()
        except ValueError:
            # 如果不是数字，尝试用 field_name 查找
            field = CustomField.query.filter_by(
                resource_type='host',
                field_name=key
            ).first()
        
        if not field:
            raise KeyError(key)
        
        # 查询对应资源的字段值
        field_value = CustomFieldValue.query.filter_by(
            field_id=field.id,
            resource_id=self.id
        ).first()
        
        if not field_value:
            return None
        
        # 按字段类型返回对应值
        if field.field_type == 'int':
            return field_value.int_value
        elif field.field_type == 'varchar':
            return field_value.varchar_value
        elif field.field_type == 'datetime':
            return field_value.datetime_value
        elif field.field_type == 'enum':
            from app.models import CustomFieldEnumOption
            enum_opt = CustomFieldEnumOption.query.filter_by(
                field_id=field.id,
                option_key=field_value.enum_value
            ).first()
            return enum_opt.option_label if enum_opt else field_value.enum_value
        
        return None

    def __repr__(self):
        return f"<Host {self.host_info}>"

class VM(db.Model):
    __tablename__ = 'vms'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='虚拟机id,自增主键')
    vm_ip = db.Column(db.String(15), unique=True, nullable=False, comment='虚拟机IP地址')
    cpus = db.Column(db.Integer, nullable=True, comment='cpu数量')
    memory_gb = db.Column(db.Integer, nullable=True, comment='内存大小(GB)')
    disk_gb = db.Column(db.Integer, nullable=True, comment='磁盘大小(GB)')
    domain_name = db.Column(db.String(20), nullable=True, comment='虚拟机域名')
    os_type = db.Column(db.String(100), nullable=False, comment='操作系统类型')
    vm_user = db.Column(db.String(100), nullable=False, comment='虚拟机登录用户名')
    host_id = db.Column(db.Integer, db.ForeignKey('hosts.id', ondelete='CASCADE'), nullable=False, comment='所属宿主机ID,关联hosts表的id')
    status = db.Column(ENUM('running', 'stopped', 'unknown', name='vm_status_enum'), nullable=False, server_default='unknown', comment='虚拟机状态')
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间,自动维护')

    # 关系：VM属于一个主机
    host = db.relationship('Host', back_populates='vms')

    def __getitem__(self, key):
        """支持通过字典访问方式获取自定义字段值（重构后适配新表结构）"""
        from app.models import CustomField, CustomFieldValue
        
        # 先尝试获取原生字段
        try:
            return getattr(self, key)
        except AttributeError:
            pass
        
        # 查找自定义字段 - 先尝试用 id 查找，再尝试用 field_name 查找
        field = None
        try:
            field_id = int(key)
            field = CustomField.query.filter_by(
                resource_type='vm',
                id=field_id
            ).first()
        except ValueError:
            # 如果不是数字，尝试用 field_name 查找
            field = CustomField.query.filter_by(
                resource_type='vm',
                field_name=key
            ).first()
        
        if not field:
            raise KeyError(key)
        
        # 查询对应资源的字段值
        field_value = CustomFieldValue.query.filter_by(
            field_id=field.id,
            resource_id=self.id
        ).first()
        
        if not field_value:
            return None
        
        # 按字段类型返回对应值
        if field.field_type == 'int':
            return field_value.int_value
        elif field.field_type == 'varchar':
            return field_value.varchar_value
        elif field.field_type == 'datetime':
            return field_value.datetime_value
        elif field.field_type == 'enum':
            from app.models import CustomFieldEnumOption
            enum_opt = CustomFieldEnumOption.query.filter_by(
                field_id=field.id,
                option_key=field_value.enum_value
            ).first()
            return enum_opt.option_label if enum_opt else field_value.enum_value
        
        return None

    def __repr__(self):
        return f"<VM {self.vm_ip} on Host ID {self.host_id}>"

class ChangeLog(db.Model):
    __tablename__ = 'change_logs'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='日志ID,自增主键')
    time = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='操作时间')
    username = db.Column(db.String(255), nullable=False, comment='执行操作的用户名(保留历史值)')
    action = db.Column(ENUM('create', 'update', 'delete', name='change_action_enum'), nullable=False, comment='操作类型')
    status = db.Column(ENUM('success', 'failed', name='change_status_enum'), nullable=False, comment='操作状态')
    object_type = db.Column(ENUM('host', 'vm', 'user', name='object_type_enum'), nullable=False, comment='操作对象类型')
    object_identifier = db.Column(db.String(255), nullable=False, comment='操作对象唯一标识(如IP或ID)')
    detail = db.Column(JSON, nullable=False, comment='操作详情')

    def __repr__(self):
        return f"<ChangeLog {self.id} by {self.username}>"

class OperationLog(db.Model):
    __tablename__ = 'operation_logs'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='日志ID,自增主键')
    time = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='操作时间')
    username = db.Column(db.String(255), nullable=False, comment='执行操作的用户名(保留历史值)')
    vm_ip = db.Column(db.String(15), nullable=False, comment='操作的虚拟机IP(保留历史值)')
    action = db.Column(ENUM('start', 'shutdown', 'reboot', name='op_action_enum'), nullable=False, comment='操作类型')
    status = db.Column(ENUM('success', 'failed', name='op_status_enum'), nullable=False, comment='操作状态')
    details = db.Column(JSON, nullable=True, comment='操作详情或错误信息')

    def __repr__(self):
        return f"<OperationLog {self.action} on {self.vm_ip} by {self.username}>"

class CustomField(db.Model):
    __tablename__ = 'custom_fields'
    __table_args__ = {'comment': '自定义字段配置表'}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='字段唯一主键ID')
    resource_type = db.Column(db.String(16), nullable=False, comment='资源类型，仅允许host/vm')
    field_name = db.Column(db.String(255), nullable=False, comment='字段前端显示名称')
    field_type = db.Column(db.String(16), nullable=False, comment='字段数据类型：int/varchar/datetime/enum')
    field_length = db.Column(db.Integer, default=255, comment='字段长度限制，仅varchar生效')
    is_required = db.Column(db.SmallInteger, nullable=False, default=0, comment='是否必填，1=必填，0=选填')
    default_value = db.Column(db.String(255), nullable=True, comment='字段默认值')
    sort = db.Column(db.Integer, nullable=False, default=0, comment='前端展示排序')
    create_time = db.Column(db.DateTime, nullable=False, default=func.current_timestamp(), comment='创建时间')
    update_time = db.Column(db.DateTime, nullable=False, default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')

    # 关联枚举选项：删除字段时自动级联删除关联枚举
    enum_options = db.relationship(
        'CustomFieldEnumOption',
        backref='field',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # 关联字段值：删除字段时自动级联删除关联值
    values = db.relationship(
        'CustomFieldValue',
        backref='field',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<CustomField {self.field_name} ({self.resource_type})>"

class CustomFieldEnumOption(db.Model):
    __tablename__ = 'custom_field_enum_options'
    __table_args__ = {'comment': '自定义字段枚举选项表'}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='枚举选项唯一主键ID')
    field_id = db.Column(db.Integer, db.ForeignKey('custom_fields.id', ondelete='CASCADE'), nullable=False, comment='关联的字段ID')
    option_key = db.Column(db.String(255), nullable=False, comment='枚举选项存储值')
    option_label = db.Column(db.String(255), nullable=False, comment='枚举选项前端显示名')
    sort = db.Column(db.Integer, nullable=False, default=0, comment='选项排序')
    create_time = db.Column(db.DateTime, nullable=False, default=func.current_timestamp(), comment='创建时间')
    update_time = db.Column(db.DateTime, nullable=False, default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')

    def __repr__(self):
        return f"<CustomFieldEnumOption {self.option_label}>"

class CustomFieldValue(db.Model):
    __tablename__ = 'custom_field_values'
    __table_args__ = {'comment': '自定义字段值表'}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='值记录唯一主键ID')
    field_id = db.Column(db.Integer, db.ForeignKey('custom_fields.id', ondelete='CASCADE'), nullable=False, comment='关联的字段ID（级联删除）')
    resource_type = db.Column(db.String(16), nullable=False, comment='资源类型host/vm')
    resource_id = db.Column(db.Integer, nullable=False, comment='关联的宿主机/虚拟机ID')
    int_value = db.Column(db.BigInteger, nullable=True, comment='int类型值')
    varchar_value = db.Column(db.String(255), nullable=True, comment='varchar类型值')
    datetime_value = db.Column(db.DateTime, nullable=True, comment='datetime类型值')
    enum_value = db.Column(db.String(255), nullable=True, comment='enum类型值')
    update_time = db.Column(db.DateTime, nullable=False, default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')

    def __repr__(self):
        return f"<CustomFieldValue field_id={self.field_id} resource_id={self.resource_id}>"