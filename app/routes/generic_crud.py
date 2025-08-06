from flask import Blueprint, render_template, request, jsonify, url_for, session, redirect, flash, current_app, Response
from flask_login import login_required
from flask_sqlalchemy.pagination import Pagination
from app.models import VM, Host, User, db, ChangeLog, OperationLog
from app.services.log_service import log_change, to_dict
import json
import pytz
from functools import wraps
from datetime import datetime
from sqlalchemy import or_, inspect, cast, String, func
import csv
import ipaddress
import io
import os


generic_crud_bp = Blueprint('generic_crud', __name__, url_prefix='/')


# 模型映射表
MODEL_CONFIG = {
    # 各模型配置项说明：
    # 'field_config'：字段配置列表，每个字段包含：
    #   'db_field': 数据库真实字段名
    #   'label': 映射给前端展示的字段名称
    #   'sortable': 布尔值，是否支持排序功能
    #   'filterable': 布尔值，是否支持过滤功能
    #   （可选）'render': 自定义渲染函数，用于字段的HTML展示
    #
    # 'default_columns'：列表，前端页面默认展示的字段（对应field_config中的db_field）
    #
    # 'search_fields'：列表，支持搜索功能的字段（对应field_config中的db_field）
    #
    # 'model_name'：字符串，模型映射的名称（用于前端页面标题、提示信息等）
    #
    # 'route_base'：字符串，路由基础路径（用于生成CRUD相关接口路径，如/list、/edit等）
    #
    # 'form_fields'：表单字段配置列表，每个字段包含：
    #   'name': 数据库真实字段名
    #   'label': 映射给前端展示的表单标签
    #   'type': 表单输入类型（如text、select、number等）
    #   'required': 布尔值，是否为必填项
    #   （可选）'options': 当type为select时，下拉选项的列表
    #
    # （可选）权限控制字段（布尔值）：
    #   'no_add': 是否禁用添加功能
    #   'no_edit': 是否禁用编辑功能
    #   'no_delete': 是否禁用删除功能
    #   'no_bulk_edit': 是否禁用批量编辑功能
    #   'no_bulk_delete': 是否禁用批量删除功能
    #   'no_import': 是否禁用导入功能
    #
    # （可选）排序配置：
    #   'default_sort': 默认排序字段（对应db_field）
    #   'default_order': 默认排序方向（'asc'升序/'desc'降序）
    'vms': {
        'model': VM,
        'field_config': [
            {'db_field': 'id', 'label': 'ID', 'sortable': True, 'filterable': True},
            {'db_field': 'vm_ip', 'label': 'IP ADDRESS', 'sortable': True, 'filterable': True},
            {'db_field': 'vm_user', 'label': 'USER', 'sortable': True, 'filterable': True},
            {'db_field': 'os_type', 'label': 'OS TYPE', 'sortable': True, 'filterable': True},
            {'db_field': 'domain_name', 'label': 'DOMAIN NAME', 'sortable': True, 'filterable': True},
            {'db_field': 'status','label': 'STATUS','sortable': True, 'filterable': True},
            {
                'db_field': 'host_id',
                'label': 'HOST INFO',
                'sortable': True,
                'filterable': True,
                'render': lambda item: f'<a href="/hosts/list?id={item.host_id}" class="text-primary hover:underline">{item.host.host_info if item.host else item.host_id}</a>'
            },
            {'db_field': 'cpus', 'label': 'CPUS', 'sortable': True, 'filterable': True, },
            {'db_field': 'memory_gb', 'label': 'MEMORY(GB)', 'sortable': True, 'filterable': True,},
            {'db_field': 'disk_gb', 'label': 'DISK(GB)', 'sortable': True, 'filterable': True,},
            {'db_field': 'created_at', 'label': 'CREATED AT', 'sortable': True, 'filterable': True},
            {'db_field': 'updated_at', 'label': 'UPDATED AT', 'sortable': True, 'filterable': True}
        ],
        'default_columns': [ 'vm_ip', 'vm_user', 'os_type', 'status', 'host_id', 'domain_name',],
        'search_fields': ['vm_ip', 'vm_user', 'os_type', 'status', 'host_id', 'cpus', 'memory_gb', 'disk_gb', 'domain_name', 'created_at', 'updated_at'],
        'model_name': 'VMs',
        'route_base': 'vms',
        'form_fields': [
            {'name': 'vm_user', 'label': 'USER', 'type': 'text', 'required': True},
            {'name': 'vm_ip', 'label': 'IP ADDRESS', 'type': 'text', 'required': True},
            {'name': 'os_type', 'label': 'OS TYPE', 'type': 'text', 'required': True},
            {'name': 'status', 'label': 'STATUS', 'type': 'select', 'options': ['active', 'inactive'],'required': True},
            {'name': 'host_id', 'label': 'HOST INFO', 'type': 'select', 'required': True},
            {'name': 'cpus', 'label': 'CPUS', 'type': 'number', 'required': False},
            {'name': 'memory_gb', 'label': 'MEMORY(GB)', 'type': 'number', 'required': False},
            {'name': 'disk_gb', 'label': 'DISK(GB)', 'type': 'number', 'required': False},
            {'name': 'domain_name', 'label': 'DOMAIN NAME', 'type': 'text', 'required': False}
        ],
        'default_sort': 'vm_ip'
    },
    'hosts': {
        'model': Host,
        'field_config': [
            {'db_field': 'id', 'label': 'ID', 'sortable': True, 'filterable': True},
            {'db_field': 'host_info', 'label': 'HOST INFO', 'sortable': True, 'filterable': True},
            {
                'db_field': 'vm_count',
                'label': 'VM COUNTS',
                'sortable': True,
                'filterable': True,
                'render': lambda item: f'<a href="/vms/list?host_id={item.id}" class="text-primary hover:underline">{item.vm_count}</a>'
            },
            {'db_field': 'status','label': 'STATUS','sortable': True, 'filterable': True},
            {'db_field': 'department', 'label': 'DEPARTMENT', 'sortable': True, 'filterable': True},
            {'db_field': 'virtualization_type', 'label': 'TYPE', 'sortable': True, 'filterable': True},
            {'db_field': 'created_at', 'label': 'CREATED AT', 'sortable': True, 'filterable': True},
            {'db_field': 'updated_at', 'label': 'UPDATED AT', 'sortable': True, 'filterable': True},
        ],
        'default_columns': ['host_info', 'status', 'department', 'virtualization_type', 'vm_count'],
        'search_fields': ['id', 'host_info', 'status', 'department', 'virtualization_type', 'vm_count', 'created_at', 'updated_at'],
        'model_name': 'Hosts',
        'route_base': 'hosts',
        'form_fields': [
            {'name': 'host_info', 'label': 'HOST INFO', 'type': 'text', 'required': True},
            {'name': 'department', 'label': 'DEPARTMENT', 'type': 'text', 'required': True},
            {'name': 'status', 'label': 'STATUS', 'type': 'select', 'options': ['active', 'inactive'], 'required': True},
            {'name': 'virtualization_type', 'label': 'TYPE','type': 'select','options': ['pve', 'kvm'], 'required': True}  
        ]
    },
    'change_logs': {
        'model': ChangeLog,
        'field_config': [
            {'db_field': 'id', 'label': 'ID', 'sortable': True, 'filterable': False},
            {'db_field': 'time', 'label': 'TIME', 'sortable': True, 'filterable': True},
            {'db_field': 'username', 'label': 'USER', 'sortable': True, 'filterable': True},
            {'db_field': 'action', 'label': 'ACTION', 'sortable': True, 'filterable': True},
            {'db_field': 'status', 'label': 'STATUS', 'sortable': True, 'filterable': True},
            {'db_field': 'object_type', 'label': 'OBJECT TYPE', 'sortable': True, 'filterable': True},
            {
                'db_field': 'object_identifier', 
                'label': 'OBJECT IDENTIFIER', 
                'sortable': True, 
                'filterable': True,
                'render': lambda item: get_object_identifier_link(item.object_type, item.object_identifier)
            },
            {'db_field': 'detail', 'label': 'DETAILS', 'sortable': False, 'filterable': False, 
             'render': lambda item: (
                 '<div class="details-container">'
                 f'<button class="details-button text-white bg-blue-500 hover:bg-blue-600 focus:ring-4 focus:ring-blue-300 font-medium rounded-lg text-xs px-3 py-1.5">View</button>'
                 f'<div class="details-content hidden relative mt-2">'
                 f'    <button class="close-details-button absolute top-0 right-0 p-1 text-gray-500 hover:text-gray-800 text-lg leading-none">&times;</button>'
                 f'    <pre class="text-xs w-full overflow-x-auto bg-gray-100 p-2 rounded">{json.dumps(item.detail, ensure_ascii=False, indent=2)}</pre>'
                 f'</div>'
                 '</div>'
             ) if item.detail else ''
            }
        ],
        'default_columns': ['time', 'username', 'action', 'status', 'object_type', 'object_identifier', 'detail'],
        'search_fields': ['time', 'username', 'action', 'status', 'object_type', 'object_identifier', 'id', 'detail'],
        'model_name': 'Change_logs',
        'route_base': 'change_logs',
        'form_fields': [],
        'default_sort': 'id',
        'default_order': 'desc',
        'no_add': True,
        'no_edit': True,
        'no_delete': True,
        'no_bulk_edit': True,
        'no_bulk_delete': True,
        'no_import': True
    },
    'operation_logs': {
        'model': OperationLog,
        'field_config': [
            {'db_field': 'id', 'label': 'ID', 'sortable': True, 'filterable': False},
            {'db_field': 'time', 'label': 'TIME', 'sortable': True, 'filterable': True},
            {'db_field': 'username', 'label': 'USER', 'sortable': True, 'filterable': True},
            {'db_field': 'vm_ip', 'label': 'VM IP', 'sortable': True, 'filterable': True},
            {'db_field': 'action', 'label': 'ACTION', 'sortable': True, 'filterable': True},
            {'db_field': 'status', 'label': 'STATUS', 'sortable': True, 'filterable': True},
            {'db_field': 'details', 'label': 'DETAILS', 'sortable': False, 'filterable': False, 
             'render': lambda item: (
                 '<div class="details-container">'
                 f'<button class="details-button text-white bg-blue-500 hover:bg-blue-600 focus:ring-4 focus:ring-blue-300 font-medium rounded-lg text-xs px-3 py-1.5">View</button>'
                 f'<div class="details-content hidden relative mt-2">'
                 f'    <button class="close-details-button absolute top-0 right-0 p-1 text-gray-500 hover:text-gray-800 text-lg leading-none">&times;</button>'
                 f'    <pre class="text-xs w-full overflow-x-auto bg-gray-100 p-2 rounded">{json.dumps(item.details, ensure_ascii=False, indent=2)}</pre>'
                 f'</div>'
                 '</div>'
             ) if item.details else ''
            }
        ],
        'default_columns': ['time', 'vm_ip', 'username', 'action', 'status', 'duration_seconds', 'details'],
        'search_fields': ['action', 'status'],
        'model_name': 'Operation_logs',
        'route_base': 'operation_logs',
        'form_fields': [],
        'default_sort': 'id',
        'default_order': 'desc',
        'no_add': True,
        'no_edit': True,
        'no_delete': True,
        'no_bulk_edit': True,
        'no_bulk_delete': True,
        'no_import': True
    },
    'users': {
        'model': User,
        'field_config': [
            {'db_field': 'id', 'label': 'ID', 'sortable': True, 'filterable': False},
            {'db_field': 'username', 'label': 'USERNAME', 'sortable': True, 'filterable': True},
            {'db_field': 'role', 'label': 'ROLE', 'sortable': True, 'filterable': True},
            {'db_field': 'created_at', 'label': 'CREATED AT', 'sortable': True, 'filterable': True},
            {'db_field': 'last_login', 'label': 'LAST LOGIN AT', 'sortable': True, 'filterable': True},
        ],
        'default_columns': ['username', 'role', 'created_at', 'last_login'],
        'search_fields': ['id', 'username', 'role', 'created_at', 'last_login'],
        'model_name': 'Users',
        'route_base': 'users',
        'form_fields': [
            {'name': 'role', 'label': 'ROLE', 'type': 'select', 'options': ['admin', 'manager','operator'],'required': True},
        ],
        'no_add': True,
        'no_bulk_edit': True,
        'no_bulk_delete': True,
        'no_import': True
    },
}


def get_object_identifier_link(object_type, object_identifier):
    if object_type == 'vm':  
        return f'<a href="/vms/list?vm_ip={object_identifier}" class="text-primary hover:underline">{object_identifier}</a>'
    elif object_type == 'host':
        host = Host.query.get(object_identifier)
        display_text = host.host_info if host else object_identifier
        # 使用host_info作为过滤参数
        return f'<a href="/hosts/list?host_info={host.host_info if host else object_identifier}" class="text-primary hover:underline">{display_text}</a>'
    elif object_type == 'user':
        # user类型超链接
        return f'<a href="/users/list?username={object_identifier}" class="text-primary hover:underline">{object_identifier}</a>'
    else:
        return object_identifier


def get_model_config(model_name):
    return MODEL_CONFIG.get(model_name)


def require_model(f):
    @wraps(f)
    def wrapper(model_name, *args, **kwargs):
        config = get_model_config(model_name)
        if not config:
            return jsonify({'error': 'Model not found'}), 404
        return f(config, model_name, *args, **kwargs)
    return wrapper


def get_query_data(config, include_pagination=True):
    model = config['model']
    field_config = config['field_config']   
    sort = request.args.get('sort', config.get('default_sort', 'id'))
    order = request.args.get('order', config.get('default_order', 'asc'))
    search = request.args.get('search', '').strip()
    query = model.query
    
    # 处理搜索
    if search and config.get('search_fields'):
        conditions = []
        for field in config.get('search_fields', []):
            column = getattr(model, field, None)
            if column:
                conditions.append(cast(column, String).ilike(f'{search}%'))
        if conditions:
            query = query.filter(or_(*conditions))
    
    # 处理过滤参数
    filter_mapping = {
        'search': None,
        'page': None,
        'per_page': None,
        'sort': None,
        'order': None,
        'visible_columns': None
    }
    
    for field in field_config:
        if field.get('filterable', False):
            filter_mapping[field['db_field']] = field['db_field']
    
    for param_name, field_name in filter_mapping.items():
        if not field_name:
            continue
            
        filter_value = request.args.get(param_name)
        if filter_value:
            column = getattr(model, field_name, None)
            if column:
                values = filter_value.split(',')
                if '__NULL__' in values:
                    other_values = [v for v in values if v != '__NULL__']
                    null_check = or_(column.is_(None), column == '')
                    if other_values:
                        query = query.filter(or_(null_check, column.in_(other_values)))
                    else:
                        query = query.filter(null_check)
                elif len(values) > 1:
                    query = query.filter(column.in_(values))
                else:
                    single_value = values[0]
                    if isinstance(column.type, db.DateTime):
                        date_val = None
                        try:
                            date_val = datetime.strptime(single_value, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            current_app.logger.warning(f"Could not parse date '{single_value}'")
                        
                        if date_val:
                            query = query.filter(column == date_val)
                    else:
                        query = query.filter(column.ilike(f'{single_value}'))
    
    # 处理排序
    valid_sort_fields = [f['db_field'] for f in field_config if f.get('sortable', False)]
    if sort in valid_sort_fields:
        sort_column = getattr(model, sort)
        if sort in ('vm_ip'):
            order_expr = func.inet_aton(sort_column)
        else:
            order_expr = sort_column
   
        if order.lower() == 'asc':
            query = query.order_by(order_expr.asc())
        else:
            query = query.order_by(order_expr.desc())
    
    if include_pagination:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        start = (pagination.page - 1) * pagination.per_page + 1 if pagination.total > 0 else 0
        end = min(start + pagination.per_page - 1, pagination.total)
        
        return {
            'items': pagination.items,
            'pagination': pagination,
            'pagination_info': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next,
                'prev_num': pagination.prev_num,
                'next_num': pagination.next_num,
                'start': start,
                'end': end
            },
            'filter_params': {k: v for k, v in request.args.items() if k in filter_mapping and v},
            'search': search,
            'sort_by': sort,
            'sort_order': order
        }
    else:
        items = query.all()
        return {
            'items': items,
            'search': search,
            'sort_by': sort,
            'sort_order': order,
            'filter_params': {k: v for k, v in request.args.items() if k in filter_mapping and v}
        }


def get_paginated_data(config, search_fields=None):
    return get_query_data(config, include_pagination=True)


def is_valid_ipv4(ip_str):
    try:
        ipaddress.IPv4Address(ip_str)
        return True
    except (ValueError, TypeError):
        return False


@generic_crud_bp.route('/<model_name>/list')
@login_required
@require_model
def list_view(config, model_name):
    route_base = config['route_base']

    user_id = session.get('_user_id')
    user_settings = get_user_table_settings(user_id, model_name) 
    user_visible_columns = user_settings.get('visible_columns')

    visible_columns_str = request.args.get('visible_columns')
    if visible_columns_str:
        visible_columns = visible_columns_str.split(',')
    elif user_visible_columns:
        visible_columns = user_visible_columns
    else:
        visible_columns = config['default_columns']

    valid_columns = [f['db_field'] for f in config['field_config']]
    visible_columns = [col for col in visible_columns if col in valid_columns]
    if not visible_columns:
        visible_columns = config['default_columns']

    form_fields = config.get('form_fields', [])
    if model_name == 'vms':
        hosts = Host.query.all()
        host_options = [(host.host_info) for host in hosts]
        for field in form_fields:
            if field['name'] == 'host_id':
                field['options'] = host_options

    query_data = get_paginated_data(
        config,
        search_fields=config.get('search_fields', [])
    )

    visible_fields = [f for f in config['field_config'] if f['db_field'] in visible_columns]
    visible_fields.sort(key=lambda x: visible_columns.index(x['db_field']))

    serializable_field_config = serialize_field_config(config['field_config'])
    
    no_add = config.get('no_add', False)
    no_edit = config.get('no_edit', False)
    no_delete = config.get('no_delete', False)
    no_bulk_edit = config.get('no_bulk_edit', False)
    no_bulk_delete = config.get('no_bulk_delete', False)
    no_import = config.get('no_import', False)
    
    active_page = route_base
    
    data_open = model_name in ['vms', 'hosts']
    logs_open = model_name in ['change_logs', 'operation_logs']
    admin_open = model_name in ['users']

    return render_template(
        'generic/list.html',
        items=query_data['items'],
        pagination=query_data['pagination'],
        pagination_info=query_data['pagination_info'],
        filter_params=query_data['filter_params'],
        search=query_data['search'],
        sort_by=query_data['sort_by'],
        sort_order=query_data['sort_order'],
        field_config=config['field_config'],
        visible_fields=visible_fields,
        visible_columns=visible_columns,
        default_columns=config['default_columns'],
        serializable_field_config=serializable_field_config,
        model_name=config['model_name'],
        route_base=route_base,
        active_page=active_page,
        user_settings=user_settings,
        data_open=data_open,
        logs_open=logs_open,
        admin_open=admin_open,
        form_fields=form_fields,
        no_add=no_add,
        no_edit=no_edit,
        no_delete=no_delete,
        no_bulk_edit=no_bulk_edit,
        no_bulk_delete=no_bulk_delete,
        no_import=no_import
    )


@generic_crud_bp.route('/<model_name>/create', methods=['GET', 'POST'])
@login_required
@require_model
def create_view(config, model_name):
    model = config['model']
    form_fields = config['form_fields']
    
    if model_name == 'vms':
        hosts = Host.query.all()
        host_options = [(host.host_info) for host in hosts]
        for field in form_fields:
            if field['name'] == 'host_id':
                field['label'] = 'HOST INFO'
                field['type'] = 'select'
                field['options'] = host_options
    
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        errors = {}
        for field in form_fields:
            if field.get('required') and not data.get(field['name']):
                errors[field['name']] = f"{field['label']}is a required field"
        
        if model_name == 'hosts' and 'host_info' in data:
            host_info = data['host_info'].strip()
            existing_host = model.query.filter_by(host_info=host_info).first()
            if existing_host:
                errors['host_info'] = f"Host '{host_info}' already exists."
        
        host_id = None
        if model_name == 'vms' and 'host_id' in data:
            host_info = data['host_id']
            host = Host.query.filter_by(host_info=host_info).first()
            if not host:
                errors['host_id'] = f"Host '{host_info}' not found."
            else:
                host_id = host.id
        
        if model_name == 'vms' and 'vm_ip' in data:
            vm_ip = data['vm_ip']
            if vm_ip and not is_valid_ipv4(vm_ip):
                errors['vm_ip'] = f"IP address '{vm_ip}' is not a valid IPv4 format."
        
        if errors:
            if request.is_json:
                return jsonify({
                    'success': False, 
                    'message': 'Please fill in all required fields and ensure that the data is formatted correctly', 
                    'errors': errors
                }), 400
            else:
                for field, error in errors.items():
                    flash(error, 'error')
                return render_template('generic/form.html',
                                    model_name=config['model_name'],
                                    form_fields=form_fields,
                                    data=data,
                                    route_base=config['route_base'],
                                    active_page=config['route_base'])
        
        new_item = model()
        for field in form_fields:
            field_name = field['name']
            if field_name not in data:
                continue
                
            if model_name == 'vms' and field_name == 'host_id':
                setattr(new_item, field_name, host_id)
                continue
                
            if field['type'] == 'boolean':
                value = data[field_name]
                if isinstance(value, str):
                    value = value.lower() in ('true', 'yes', '1', 'on')
                setattr(new_item, field_name, value)
            elif field['type'] == 'number':
                try:
                    value = float(data[field_name]) if data[field_name] else None
                    setattr(new_item, field_name, value)
                except ValueError:
                    if request.is_json:
                        return jsonify({
                            'success': False,
                            'message': f"{field['label']} must be a number"
                        }), 400
                    else:
                        flash(f"{field['label']} must be a number", 'error')
                        return render_template('generic/form.html',
                                            model_name=config['model_name'],
                                            form_fields=form_fields,
                                            data=data,
                                            route_base=config['route_base'],
                                            active_page=config['route_base'])
            else:
                setattr(new_item, field_name, data[field_name])
        
        beijing_tz = pytz.timezone('Asia/Shanghai')
        if hasattr(new_item, 'created_at'):
            new_item.created_at = datetime.now(beijing_tz)
        
        try:
            db.session.add(new_item)
            db.session.flush()

            if model_name == 'vms':
                identifier = getattr(new_item, 'vm_ip', str(new_item.id))
                host = Host.query.get(new_item.host_id)
                host_info = host.host_info
                detail_with_host = {
                    'vm_details': to_dict(new_item),
                    'host_relation': {
                        'host_info': host_info
                    }                    
                }
            elif model_name == 'hosts':
                identifier = getattr(new_item, 'host_info', str(new_item.id))
                detail_with_host = {'host_details': to_dict(new_item)}
            elif model_name == 'user':
                identifier = getattr(new_item, 'username', str(new_item.id))
                detail_with_host = to_dict(new_item)
            else:
                identifier = getattr(new_item, 'host_info', getattr(new_item, 'vm_ip', new_item.id))
                detail_with_host = to_dict(new_item)
            log_change('created', model_name, identifier, detail_obj=detail_with_host)
            
            db.session.commit()

            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': f"{config['model_name']} created successfully",
                    'id': new_item.id
                })
            else:
                flash(f"{config['model_name']} created successfully", 'success')
                return redirect(url_for('generic_crud.list_view', model_name=model_name))
                
        except Exception as e:
            db.session.rollback()
            identifier = data.get('host_id') or data.get('vm_ip') or 'N/A'
            log_change('created', model_name, identifier, status='failed', detail_obj=data)
            error_msg = f"create failed: {str(e)}"
            
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': error_msg
                }), 500
            else:
                flash(error_msg, 'error')
    
    return render_template('generic/form.html',
                           model_name=config['model_name'],
                           form_fields=form_fields,
                           data={},
                           route_base=config['route_base'],
                           active_page=config['route_base'])


@generic_crud_bp.route('/<model_name>/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@require_model
def edit_view(config, model_name, id):
    model = config['model']
    item = model.query.get_or_404(id)
    form_fields = config['form_fields']
    
    # 确保表单字段配置存在
    if not form_fields:
        flash(f"No editable fields configured for {config['model_name']}", 'error')
        return redirect(url_for('generic_crud.list_view', model_name=model_name))
    
    if model_name == 'vms':
        hosts = Host.query.all()
        host_options = [(host.host_info) for host in hosts]
        for field in form_fields:
            if field['name'] == 'host_id':
                field['type'] = 'select'
                field['options'] = host_options
    
    if request.method == 'POST':
        # 统一获取数据，确保即使空值也能被正确处理
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
        
        errors = {}
        # 验证必填字段
        for field in form_fields:
            field_name = field['name']
            field_value = data.get(field_name)
            
            # 检查必填字段
            if field.get('required'):
                # 处理空字符串和None的情况
                if field_value in (None, '', ' '):
                    errors[field_name] = f"{field['label']} is a required field"
        
        # 模型特定验证
        if model_name == 'hosts' and 'host_info' in data:
            host_info = data['host_info'].strip()
            existing_host = model.query.filter_by(host_info=host_info).first()
            if existing_host and existing_host.id != id:
                errors['host_info'] = f"Host '{host_info}' already exists."
        
        if model_name == 'vms':
            # 处理主机ID转换
            host_id = None
            if 'host_id' in data:
                host_info = data['host_id']
                if host_info:
                    host = Host.query.filter_by(host_info=host_info).first()
                    if not host:
                        errors['host_id'] = f"Host '{host_info}' not found."
                    else:
                        host_id = host.id
                else:
                    if any(f['name'] == 'host_id' and f.get('required') for f in form_fields):
                        errors['host_id'] = "Host is required"
            
            # 验证VM IP
            if 'vm_ip' in data:
                vm_ip = data['vm_ip']
                if vm_ip and not is_valid_ipv4(vm_ip):
                    errors['vm_ip'] = f"IP address '{vm_ip}' is not a valid IPv4 format."
                else:
                    existing_vm = VM.query.filter_by(vm_ip=vm_ip).first()
                    if existing_vm and existing_vm.id != id:
                        errors['vm_ip'] = f"VM with IP '{vm_ip}' already exists."
        
        # 数字字段验证
        for field in form_fields:
            field_name = field['name']
            if field.get('type') == 'number' and field_name in data:
                value_str = data.get(field_name)
                if value_str:
                    try:
                        if float(value_str) < 0:
                            errors[field_name] = f"{field['label']} must be a non-negative number."
                    except (ValueError, TypeError):
                        errors[field_name] = f"{field['label']} must be a valid number."

        # 处理错误
        if errors:
            try:
                changes = []
                for field_name in [f['name'] for f in form_fields]:
                    old_value = getattr(item, field_name, 'N/A')
                    new_value = data.get(field_name, 'N/A')
                    error_msg = errors.get(field_name, '')
                    changes.append({
                        'field': field_name,
                        'old_value': old_value,
                        'new_value': new_value,
                        'error': error_msg
                    })
                
                # 确定标识符
                if model_name == 'vms':
                    identifier = getattr(item, 'vm_ip', str(item.id))
                elif model_name == 'hosts':
                    identifier = getattr(item, 'host_info', str(item.id))
                elif model_name == 'users':
                    identifier = getattr(item, 'username', str(item.id))
                else:
                    identifier = str(item.id)
                
                log_detail = {'changes': changes, 'error': True}
                log_change('updated', model_name, identifier, status='failed', detail_obj=log_detail)
                db.session.commit()
            except Exception as log_error:
                current_app.logger.error(f"Failed to log change attempt: {str(log_error)}")
            
            if request.is_json:
                return jsonify({
                    'success': False, 
                    'message': 'Validation errors', 
                    'errors': errors
                }), 400
            else:
                for field, error in errors.items():
                    flash(error, 'error')
                return render_template('generic/form.html',
                                    model_name=config['model_name'],
                                    form_fields=form_fields,
                                    data=data,
                                    item=item,
                                    route_base=config['route_base'],
                                    active_page=config['route_base'])

        # 处理字段更新
        changes = []
        mapper = inspect(model)
        field_names = [f['name'] for f in form_fields]
        
        for field in form_fields:
            field_name = field['name']
            field_type = field.get('type')
            
            # 获取旧值
            old_value = getattr(item, field_name)
            
            # 确定新值 - 确保所有字段都被处理，即使值为空
            new_value = old_value  # 默认不变
            field_value = data.get(field_name, '')
            
            # 特殊处理主机ID
            if model_name == 'vms' and field_name == 'host_id':
                new_value = host_id
            elif field_type == 'boolean':
                # 复选框处理
                new_value = field_name in data
            elif field_type == 'number':
                # 数字处理
                is_nullable = mapper.columns[field_name].nullable
                if field_value == '':
                    new_value = None if is_nullable else 0
                else:
                    try:
                        num_val = float(field_value)
                        new_value = int(num_val) if num_val.is_integer() else num_val
                    except (ValueError, TypeError):
                        new_value = old_value  # 保留旧值
            elif field_type in ('text', 'select'):
                # 文本和下拉框处理
                is_nullable = mapper.columns[field_name].nullable
                if field_value.strip() == '' and is_nullable:
                    new_value = ''
                else:
                    new_value = field_value
            
            # 检测实际变化（处理不同类型比较问题）
            value_changed = False
            if isinstance(old_value, datetime) and isinstance(new_value, str):
                # 日期时间比较
                try:
                    new_val_dt = datetime.strptime(new_value, '%Y-%m-%d %H:%M:%S')
                    value_changed = old_value != new_val_dt
                except ValueError:
                    value_changed = True
            elif old_value != new_value:
                # 普通值比较
                value_changed = True
            
            # 记录变更并更新
            if value_changed:
                changes.append({
                    'field': field_name,
                    'old_value': old_value,
                    'new_value': new_value
                })
                setattr(item, field_name, new_value)
        
        # 更新时间戳
        beijing_tz = pytz.timezone('Asia/Shanghai')
        if hasattr(item, 'updated_at'):
            item.updated_at = datetime.now(beijing_tz)
        
        try:
            # 只有有实际变更时才记录日志
            if changes:
                # 确定标识符
                if model_name == 'vms':
                    identifier = getattr(item, 'vm_ip', str(item.id))
                    # 处理主机信息变更日志
                    has_host_id_change = any(c['field'] == 'host_id' for c in changes)
                    if has_host_id_change:
                        host_id_changes = [c for c in changes if c['field'] == 'host_id'][0]
                        old_host = Host.query.get(host_id_changes['old_value']) if host_id_changes['old_value'] else None
                        new_host = Host.query.get(host_id_changes['new_value']) if host_id_changes['new_value'] else None
                        old_host_info = old_host.host_info if old_host else 'Unknown'
                        new_host_info = new_host.host_info if new_host else 'Unknown'
                        
                        if old_host_info != new_host_info:
                            changes.append({
                                'field': 'host_info',
                                'old_value': old_host_info,
                                'new_value': new_host_info
                            })
                elif model_name == 'hosts':
                    identifier = getattr(item, 'host_info', str(item.id))
                elif model_name == 'users':
                    identifier = getattr(item, 'username', str(item.id))
                else:
                    identifier = str(item.id)
                
                log_change('updated', model_name, identifier, detail_obj={'changes': changes})
            
            # 确保提交事务
            db.session.commit()

            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': f"{config['model_name']} updated successfully",
                    'id': item.id,
                    'changes': len(changes)
                })
            else:
                flash(f"{config['model_name']} updated successfully. {len(changes)} field(s) changed.", 'success')
                return redirect(url_for('generic_crud.list_view', model_name=model_name))
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Edit failed: {str(e)}", exc_info=True)
            identifier = getattr(item, 'host_info', getattr(item, 'vm_ip', str(item.id)))
            log_change('updated', model_name, identifier, status='failed', detail_obj={'error': str(e)})
            
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': f"Update failed: {str(e)}"
                }), 500
            else:
                flash(f"Update failed: {str(e)}", 'error')
    
    # 加载表单数据（GET请求）
    data = {}
    for field in form_fields:
        field_name = field['name']
        if model_name == 'vms' and field_name == 'host_id':
            # 显示主机信息而非ID
            data[field_name] = item.host.host_info if (item.host and item.host.host_info) else ''
        else:
            value = getattr(item, field_name)
            # 格式化日期时间显示
            if isinstance(value, datetime):
                data[field_name] = value.strftime('%Y-%m-%d %H:%M:%S')
            else:
                data[field_name] = value
    
    return render_template('generic/form.html',
                           model_name=config['model_name'],
                           form_fields=form_fields,
                           data=data,
                           item=item,
                           route_base=config['route_base'],
                           active_page=config['route_base'])



@generic_crud_bp.route('/<model_name>/<int:id>/delete', methods=['POST'])
@login_required
@require_model
def delete_view(config, model_name, id):
    model = config['model']
    item = model.query.get_or_404(id)
    
    if model_name == 'vms':
        identifier = getattr(item, 'vm_ip', str(item.id))
        host = Host.query.get(item.host_id) if item.host_id else None
        item_details = {
            'vm_details': to_dict(item),
            'host_relation': {
                'host_info': host.host_info
            }
        }
    elif model_name == 'hosts':
        identifier = getattr(item, 'host_info', str(item.id))
        item_details = to_dict(item)
    elif model_name == 'users':
        identifier = getattr(item, 'username', str(item.id))
        item_details = to_dict(item)
    else:
        identifier = getattr(item, 'host_info', getattr(item, 'vm_ip', str(item.id)))
        item_details = to_dict(item)

    if model_name == 'users' and 'field_config' in config:
        allowed_fields = [field['db_field'] for field in config['field_config']]
        full_details = to_dict(item)
        item_details = {k: v for k, v in full_details.items() if k in allowed_fields}

    try:
        if model_name == 'hosts' and hasattr(item, 'vms'):
            for vm in item.vms:
                vm_host_info = item.host_info if item else 'Unknown'
                vm_details = {
                    'vm_details': to_dict(vm),
                    'host_relation': {
                        'host_id': item.id if item else None,
                        'host_info': vm_host_info
                    }
                }
                log_change('deleted', 'vms', vm.vm_ip, detail_obj=vm_details)

        log_change('deleted', model_name, identifier, detail_obj=item_details)
        
        db.session.delete(item)
        db.session.commit()

        flash(f'{config["model_name"]} deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        log_change('deleted', model_name, identifier, status='failed', detail_obj=item_details)
        flash(f'{config["model_name"]} deletion failed: {str(e)}', 'error')

    return redirect(url_for('generic_crud.list_view', model_name=model_name))


# 1. 首先修改获取过滤选项的API，确保host_id显示为host_info
@generic_crud_bp.route('/<model_name>/api/filter-options')
@login_required
@require_model
def get_filter_options(config, model_name):
    field_name = request.args.get('field')
    if not field_name:
        return jsonify({'error': 'Field name is required'}), 400

    model = config['model']
    column = getattr(model, field_name, None)
    if column is None:
        return jsonify({'error': 'Invalid field name'}), 400

    # 获取当前已有的过滤条件，用于联动过滤
    current_filters = {k: v for k, v in request.args.items() if k not in ['field', 'page', 'per_page', 'sort', 'order']}
    
    # 基础查询
    query = db.session.query(column).distinct()
    
    # 应用当前已有的过滤条件，实现联动
    if current_filters:
        for filter_field, filter_value in current_filters.items():
            # 跳过当前正在查询选项的字段
            if filter_field == field_name:
                continue
                
            filter_column = getattr(model, filter_field, None)
            if filter_column:
                values = filter_value.split(',')
                if '__NULL__' in values:
                    other_values = [v for v in values if v != '__NULL__']
                    null_check = or_(filter_column.is_(None), filter_column == '')
                    if other_values:
                        query = query.filter(or_(null_check, filter_column.in_(other_values)))
                    else:
                        query = query.filter(null_check)
                elif len(values) > 1:
                    query = query.filter(filter_column.in_(values))
                else:
                    # 所有字段都使用精确匹配
                    query = query.filter(filter_column == values[0])

    options = query.all()
    response_options = []
    has_null_or_empty = False

    # 处理host_id特殊情况，显示host_info而非ID
    if field_name == 'host_id' and model_name == 'vms':
        # 预加载所有host信息用于映射
        host_map = {host.id: host.host_info for host in Host.query.all()}
        for opt in options:
            host_id = opt[0]
            if host_id is None or host_id == '':
                has_null_or_empty = True
                continue
            # 使用host_info代替id显示
            host_info = host_map.get(host_id, f"Unknown host (ID: {host_id})")
            response_options.append({'value': str(host_id), 'label': host_info})
    else:
        # 处理其他字段
        is_datetime = isinstance(column.type, db.DateTime)
        for opt in options:
            value = opt[0]
            if value is None or value == '':
                has_null_or_empty = True
                continue

            if is_datetime:
                label = value.strftime('%Y-%m-%d %H:%M:%S')
                response_options.append({'value': label, 'label': label})
            else:
                response_options.append({'value': str(value), 'label': str(value)})

    # 排序并去重
    response_options.sort(key=lambda x: x['label'])
    unique_options = {opt['value']: opt for opt in response_options}.values()
    
    # 添加空值选项
    if has_null_or_empty:
        unique_options = list(unique_options)
        unique_options.insert(0, {'value': '__NULL__', 'label': 'NULL'})

    return jsonify({'options': list(unique_options)})
    


# 2. 修改主查询逻辑，确保host_id过滤使用正确的关联条件
def get_query_data(config, include_pagination=True):
    model = config['model']
    field_config = config['field_config']   
    sort = request.args.get('sort', config.get('default_sort', 'id'))
    order = request.args.get('order', config.get('default_order', 'asc'))
    search = request.args.get('search', '').strip()
    query = model.query
    
    # 处理搜索
    if search and config.get('search_fields'):
        conditions = []
        need_join_host = False
        for field in config.get('search_fields', []):
            # 特殊处理host_id搜索，允许通过host_info搜索
            if field == 'host_id' and hasattr(model, 'host'):
                conditions.append(Host.host_info.ilike(f'%{search}%'))
                need_join_host = True  # 标记需要JOIN Host表
            else:
                column = getattr(model, field, None)
                if column:
                    conditions.append(cast(column, String).ilike(f'%{search}%'))
        if conditions:
            # 如果需要host条件，JOIN关联表
            if need_join_host:
                query = query.join(Host, model.host_id == Host.id, isouter=True)
            query = query.filter(or_(*conditions))
    
    # 处理过滤参数
    filter_mapping = {
        'search': None,
        'page': None,
        'per_page': None,
        'sort': None,
        'order': None,
        'visible_columns': None
    }
    
    for field in field_config:
        if field.get('filterable', False):
            filter_mapping[field['db_field']] = field['db_field']
    
    for param_name, field_name in filter_mapping.items():
        if not field_name:
            continue
            
        filter_value = request.args.get(param_name)
        if filter_value:
            # 特殊处理host_id过滤，允许通过host_info过滤
            if field_name == 'host_id' and hasattr(model, 'host'):
                values = filter_value.split(',')
                host_ids = []
                other_values = []
                
                for value in values:
                    if value == '__NULL__':
                        # 处理空值情况
                        null_check = or_(model.host_id.is_(None), model.host_id == '')
                        query = query.filter(null_check)
                    else:
                        # 尝试通过host_info查找对应的host_id
                        host = Host.query.filter_by(host_info=value).first()
                        if host:
                            host_ids.append(host.id)
                        else:
                            # 如果找不到对应host_info，尝试直接使用ID过滤
                            try:
                                host_id = int(value)
                                other_values.append(host_id)
                            except ValueError:
                                # 既不是有效的host_info也不是ID，跳过该值
                                pass
                
                # 合并所有有效的host_id
                all_valid_ids = host_ids + other_values
                if all_valid_ids:
                    query = query.filter(model.host_id.in_(all_valid_ids))
            else:
                column = getattr(model, field_name, None)
                if column:
                    values = filter_value.split(',')
                    if '__NULL__' in values:
                        other_values = [v for v in values if v != '__NULL__']
                        null_check = or_(column.is_(None), column == '')
                        if other_values:
                            query = query.filter(or_(null_check, column.in_(other_values)))
                        else:
                            query = query.filter(null_check)
                    elif len(values) > 1:
                        query = query.filter(column.in_(values))
                    else:
                        single_value = values[0]
                        if isinstance(column.type, db.DateTime):
                            date_val = None
                            try:
                                date_val = datetime.strptime(single_value, '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                current_app.logger.warning(f"Could not parse date '{single_value}'")
                            
                            if date_val:
                                query = query.filter(column == date_val)
                        else:
                            query = query.filter(column == single_value)
    
    # 处理排序（保持不变）
    valid_sort_fields = [f['db_field'] for f in field_config if f.get('sortable', False)]
    if sort in valid_sort_fields:
        sort_column = getattr(model, sort)
        if sort in ('vm_ip'):
            order_expr = func.inet_aton(sort_column)
        else:
            order_expr = sort_column
   
        if order.lower() == 'asc':
            query = query.order_by(order_expr.asc())
        else:
            query = query.order_by(order_expr.desc())
    
    # 分页处理（保持不变）
    if include_pagination:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        start = (pagination.page - 1) * pagination.per_page + 1 if pagination.total > 0 else 0
        end = min(start + pagination.per_page - 1, pagination.total)
        
        return {
            'items': pagination.items,
            'pagination': pagination,
            'pagination_info': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next,
                'prev_num': pagination.prev_num,
                'next_num': pagination.next_num,
                'start': start,
                'end': end
            },
            'filter_params': {k: v for k, v in request.args.items() if k in filter_mapping and v},
            'search': search,
            'sort_by': sort,
            'sort_order': order
        }
    else:
        items = query.all()
        return {
            'items': items,
            'search': search,
            'sort_by': sort,
            'sort_order': order,
            'filter_params': {k: v for k, v in request.args.items() if k in filter_mapping and v}
        }
    

@generic_crud_bp.route('/<model_name>/api/save-table-settings', methods=['POST'])
@login_required
@require_model
def save_table_settings(config, model_name):
    try:
        data = request.get_json()
    except Exception as e:
        return jsonify({'success': False, 'message': 'Invalid JSON format'}), 400
    
    visible_columns = data.get('visible_columns') or data.get('columns')
    
    if not visible_columns:
        return jsonify({'success': False, 'message': 'Missing visible_columns in data'}), 400
    
    valid_columns = [field['db_field'] for field in config['field_config']]
    visible_columns = [col for col in visible_columns if col in valid_columns]
    
    if not visible_columns:
        return jsonify({'success': False, 'message': 'No valid columns provided'}), 400
    
    user_id = session.get('_user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'User not authenticated'}), 401
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404 

    saved = save_user_table_settings(
        user_id,
        model_name,
        {'visible_columns': visible_columns}
    )
    
    if saved:
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to save settings'}), 500


def get_user_table_settings(user_id, model_name):
    if not user_id:
        return {}
    
    user = User.query.get(user_id)
    if not user:
        return {}
    
    if user.table_set:
        try:
            return user.table_set.get(model_name, {})
        except Exception as e:
            return {}
    
    return {}


def save_user_table_settings(user_id, model_name, settings):
    user = User.query.get(user_id)
    if not user:
        return False
    
    try:
        current_settings = dict(user.table_set) if isinstance(user.table_set, dict) else {}
        current_settings[model_name] = settings
        user.table_set = current_settings

        db.session.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to save table settings: {e}", exc_info=True)
        db.session.rollback()
        return False


def serialize_field_config(field_config):
    return [{k: v for k, v in field.items() if k not in ['render', 'format']} for field in field_config]


@generic_crud_bp.route('/<model_name>/bulk-delete', methods=['POST'])
@login_required
@require_model
def bulk_delete_view(config, model_name):
    model = config['model']
    data = request.get_json()
    ids_to_delete = data.get('ids')

    if not ids_to_delete:
        return jsonify({'error': 'No IDs provided'}), 400

    try:
        items_to_delete = model.query.filter(model.id.in_(ids_to_delete)).all()
        for item in items_to_delete:
            # 记录主机自身的删除日志（新增部分）
            if model_name == 'hosts':
                # 记录主机自身的删除信息
                host_identifier = getattr(item, 'host_info', str(item.id))
                host_details = {
                    'host_details': to_dict(item),
                }
                log_change('deleted', model_name, host_identifier, detail_obj=host_details)
            
            # 处理关联的VM（原逻辑保留）
            if model_name == 'vms':
                identifier = getattr(item, 'vm_ip', str(item.id))
                host = Host.query.get(item.host_id) if item.host_id else None
                vm_details = {
                    'vm_details': to_dict(item),
                    'host_relation': {
                        'host_info': host.host_info
                    }
                }
                log_change('deleted', model_name, identifier, detail_obj=vm_details)
            elif model_name == 'hosts' and hasattr(item, 'vms'):
                # 记录主机下VM的删除信息
                for vm in item.vms:
                    vm_details = {
                        'vm_details': to_dict(vm),
                        'host_relation': {
                            'host_info': item.host_info
                        }
                    }
                    log_change('deleted', 'vms', vm.vm_ip, detail_obj=vm_details)
            else:
                # 其他模型的删除日志
                identifier = getattr(item, 'host_info', getattr(item, 'vm_ip', str(item.id)))
                log_change('deleted', model_name, identifier, detail_obj=to_dict(item))

        # 执行删除操作
        model.query.filter(model.id.in_(ids_to_delete)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bulk deletion successful'})
    
    except Exception as e:
        db.session.rollback()
        log_change('deleted', model_name, f"bulk delete IDs: {ids_to_delete}", status='failed', detail_obj={'error': str(e)})
        return jsonify({'success': False, 'message': f'Bulk deletion failed: {str(e)}'}), 500


def log_bulk_edit_errors(items_to_edit, model_name, field_to_edit, new_value, errors):
    """
    为批量编辑操作中的每个项目记录错误日志
    """
    for item in items_to_edit:
        # 构建错误详情
        error_detail = {
            'error': True,
            'changes': [{
                'error': errors.get(field_to_edit, 'Validation failed'),
                'field': field_to_edit,
                'new_value': new_value,
                'old_value': getattr(item, field_to_edit, None)
            }]
        }
        
        # 根据模型类型确定标识符
        if model_name == 'vms':
            identifier = getattr(item, 'vm_ip', str(item.id))
        elif model_name == 'hosts':
            identifier = getattr(item, 'host_info', str(item.id))
        else:
            identifier = str(item.id)
        
        # 记录错误日志
        log_change('updated', model_name, identifier, status='failed', detail_obj=error_detail)
    
@generic_crud_bp.route('/<model_name>/bulk-edit', methods=['POST'])
@login_required
@require_model
def bulk_edit_view(config, model_name):
    model = config['model']
    data = request.get_json()
    ids_to_edit = data.get('ids')
    field_to_edit = data.get('field')
    new_value = data.get('value')

    # 验证必要参数
    if not all([ids_to_edit, field_to_edit]):
        return jsonify({'success': False, 'message': 'Missing required parameters'}), 400
    
    # 仅对字符串类型的值进行处理，保留数字和布尔值的原始类型
    if isinstance(new_value, str):
        # 处理包含显示文本和值的情况（提取实际值）
        if ',' in new_value:
            new_value = new_value.split(',')[0].strip()
        else:
            new_value = new_value.strip()  # 去除前后空格
    
    # 处理空值情况
    if new_value == '':
        new_value = ''

    # 获取表单配置并验证字段
    form_fields = config.get('form_fields', [])
    field_config = next((f for f in form_fields if f['name'] == field_to_edit), None)

    # 验证必填字段
    if field_config and field_config.get('required') and new_value in (None, '', ' '):
        # 获取需要编辑的项目以记录日志
        items_to_edit = model.query.filter(model.id.in_(ids_to_edit)).all()
        errors = {field_to_edit: f"Field '{field_config.get('label', field_to_edit)}' is required and cannot be empty."}
        log_bulk_edit_errors(items_to_edit, model_name, field_to_edit, new_value, errors)
        return jsonify({
            'success': False, 
            'message': f"Field '{field_config.get('label', field_to_edit)}' is required and cannot be empty."
        }), 400
    

    # 针对hosts模型的host_info字段唯一性验证
    if model_name == 'hosts' and field_to_edit == 'host_info' and new_value:
        # 查询时也使用trimmed值进行比较
        trimmed_value = new_value.strip() if isinstance(new_value, str) else new_value
        existing_host = Host.query.filter_by(host_info=trimmed_value).first()
        if existing_host and existing_host.id not in ids_to_edit:
            # 获取需要编辑的项目以记录日志
            items_to_edit = model.query.filter(model.id.in_(ids_to_edit)).all()
            errors = {field_to_edit: f"Host '{trimmed_value}' already exists"}
            log_bulk_edit_errors(items_to_edit, model_name, field_to_edit, new_value, errors)
            return jsonify({'success': False, 'message': f"Host '{trimmed_value}' already exists"}), 400

    # 针对vms模型的vm_ip格式验证
    if model_name == 'vms' and field_to_edit == 'vm_ip' and new_value:
        trimmed_value = new_value.strip() if isinstance(new_value, str) else new_value
        if not is_valid_ipv4(trimmed_value):
            # 获取需要编辑的项目以记录日志
            items_to_edit = model.query.filter(model.id.in_(ids_to_edit)).all()
            errors = {field_to_edit: f"IP address '{trimmed_value}' is not a valid IPv4 format."}
            log_bulk_edit_errors(items_to_edit, model_name, field_to_edit, new_value, errors)
            return jsonify({
                'success': False, 
                'message': f"IP address '{trimmed_value}' is not a valid IPv4 format."
            }), 400
    
    # 验证字段是否允许编辑
    if field_to_edit not in [f['name'] for f in form_fields]:
        # 获取需要编辑的项目以记录日志
        items_to_edit = model.query.filter(model.id.in_(ids_to_edit)).all()
        errors = {field_to_edit: 'Field not allowed for editing'}
        log_bulk_edit_errors(items_to_edit, model_name, field_to_edit, new_value, errors)
        return jsonify({'success': False, 'message': 'Field not allowed for editing'}), 403

    try:
        # 获取需要编辑的项目
        items_to_edit = model.query.filter(model.id.in_(ids_to_edit)).all()
        new_host_info = None
        new_host_id = None  # 初始化变量，避免未定义错误
        items_to_log = []  # 用于收集需要记录日志的项目

        # 处理host_id特殊逻辑（仅当编辑字段为host_id时）
        if model_name == 'vms' and field_to_edit == 'host_id' and new_value:
            # 处理主机信息的空格
            trimmed_host_value = new_value.strip() if isinstance(new_value, str) else new_value
            new_host = Host.query.filter_by(host_info=trimmed_host_value).first()
            if new_host:
                new_host_id = new_host.id
                new_host_info = new_host.host_info
            else:
                # 获取需要编辑的项目以记录日志
                items_to_edit = model.query.filter(model.id.in_(ids_to_edit)).all()
                errors = {field_to_edit: f"Host '{trimmed_host_value}' does not exist"}
                log_bulk_edit_errors(items_to_edit, model_name, field_to_edit, new_value, errors)
                return jsonify({'success': False, 'message': f"Host '{trimmed_host_value}' does not exist"}), 400

        # 遍历项目，收集需要记录日志的项目（仅关注当前编辑字段）
        for item in items_to_edit:
            # 获取当前字段的旧值
            old_value = getattr(item, field_to_edit)
            
            # 确定当前字段的更新值
            update_value = new_value
            if model_name == 'vms' and field_to_edit == 'host_id':
                update_value = new_host_id  # 使用实际host_id
            # 对字符串类型的更新值进行trim
            elif isinstance(update_value, str):
                update_value = update_value.strip()
            
            # 直接比较值（不转字符串），避免None误判
            if old_value == update_value:
                continue  # 无实际变化，跳过日志和更新

            # 构建变更日志（仅包含当前编辑的字段）
            detail_log = {
                'changes': [{
                    'field': field_to_edit,
                    'old_value': old_value,
                    'new_value': update_value
                }]
            }

            # 仅当编辑host_id且主机实际变化时，补充host_info变更
            if model_name == 'vms' and field_to_edit == 'host_id':
                old_host = Host.query.get(old_value) if old_value else None
                old_host_info = old_host.host_info if old_host else 'Unknown'
                # 只有新旧主机信息不同时才添加host_info日志
                if old_host_info != new_host_info:
                    detail_log['changes'].append({
                        'field': 'host_info',
                        'old_value': old_host_info,
                        'new_value': new_host_info
                    })

            # 将需要记录日志的项目和日志详情保存
            items_to_log.append((item, detail_log))
        
        # 筛选真正需要更新的ID（基于实际值变化）
        ids_to_actually_update = [
            item.id for item, _ in items_to_log
        ]
        
        # 执行实际更新操作
        if ids_to_actually_update:
            # 处理vm_ip唯一性校验
            if model_name == 'vms' and field_to_edit == 'vm_ip' and new_value:
                trimmed_value = new_value.strip() if isinstance(new_value, str) else new_value
                existing_vm = model.query.filter_by(vm_ip=trimmed_value).first()
                if existing_vm and existing_vm.id not in ids_to_edit:
                    # 为每个受影响的项目生成单独的日志
                    for item in items_to_edit:
                        identifier = getattr(item, 'vm_ip', str(item.id))
                        error_detail = {
                            'error': True,
                            'changes': [{
                                'error': f"IP address '{trimmed_value}' already exists.",
                                'field': field_to_edit,
                                'new_value': new_value,
                                'old_value': getattr(item, field_to_edit)
                            }]
                        }
                        log_change('updated', model_name, identifier, status='failed', detail_obj=error_detail)
                    
                    return jsonify({
                        'success': False, 
                        'message': f"IP address '{trimmed_value}' already exists for another VM."
                    }), 400
            
            try:
                # 执行批量更新
                model.query.filter(model.id.in_(ids_to_actually_update)).update(
                    {field_to_edit: update_value}, 
                    synchronize_session=False
                )
                db.session.commit()
                
                # 只有在成功更新后才记录日志
                for item, detail_log in items_to_log:
                    # 记录操作日志
                    if model_name == 'vms':
                        identifier = getattr(item, 'vm_ip', str(item.id))
                    elif model_name == 'hosts':
                        identifier = getattr(item, 'host_info', str(item.id))
                    else:
                        identifier = str(item.id)
                    log_change('updated', model_name, identifier, status='success', detail_obj=detail_log)
            except Exception as update_error:
                db.session.rollback()
                # 处理重复条目错误
                if 'Duplicate entry' in str(update_error):
                    error_msg = f"Bulk edit failed due to duplicate entry. "
                    if model_name == 'vms' and field_to_edit == 'vm_ip':
                        error_msg += f"IP address '{new_value}' already exists."
                        # 为每个受影响的项目生成单独的日志
                        for item, detail_log in items_to_log:
                            identifier = getattr(item, 'vm_ip', str(item.id))
                            detail_log['error'] = error_msg
                            log_change('updated', model_name, identifier, status='failed', detail_obj=detail_log)
                    else:
                        log_change(
                            'updated', model_name, f"bulk edit IDs: {ids_to_edit}", 
                            status='failed', detail_obj={'error': error_msg}
                        )
                    return jsonify({'success': False, 'message': error_msg}), 400
                else:
                    raise update_error

        return jsonify({'success': True, 'message': 'Bulk edit successful'})
    except Exception as e:
        db.session.rollback()
        log_change(
            'updated', model_name, f"bulk edit IDs: {ids_to_edit}", 
            status='failed', detail_obj={'error': str(e), 'field': field_to_edit, 'value': new_value}
        )
        return jsonify({'success': False, 'message': f'Bulk edit failed: {str(e)}'}), 500

@generic_crud_bp.route('/api/<model_name>/import', methods=['POST'])
@login_required
@require_model
def import_data_view(config, model_name):
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be CSV format'}), 400

    model = config['model']
    form_fields = config.get('form_fields', [])
    
    label_to_name_map = {field['label']: field['name'] for field in form_fields}
    required_labels = {field['label'] for field in form_fields if field.get('required')}

    try:
        stream = file.stream.read().decode('utf-8-sig')
        csv_data = list(csv.DictReader(stream.splitlines()))
        
        if not csv_data:
            return jsonify({'error': 'CSV file is empty or has no content'}), 400

        header = csv_data[0].keys()
        missing_labels = required_labels - set(header)
        if missing_labels:
            return jsonify({'error': f'CSV file is missing required columns: {", ".join(missing_labels)}'}), 400

        existing_vms_ips = set()
        existing_hosts = {}
        existing_hosts_info = set()
        unique_field_name = None
        if model_name == 'vms':
            unique_field_name = 'vm_ip'
            existing_vms_ips = {v.vm_ip for v in VM.query.with_entities(VM.vm_ip).all()}
            existing_hosts = {h.host_info: h.id for h in Host.query.with_entities(Host.host_info, Host.id).all()}
        elif model_name == 'hosts':
            unique_field_name = 'host_info'
            existing_hosts_info = {h.host_info for h in Host.query.with_entities(Host.host_info).all()}
        
        unique_field_label = next((label for label, name in label_to_name_map.items() if name == unique_field_name), None)

        # 暂存成功日志，待事务提交后再记录
        success_logs = []

        for i, row in enumerate(csv_data, start=2):
            if unique_field_label:
                identifier_value = row.get(unique_field_label)
                if model_name == 'vms' and identifier_value in existing_vms_ips:
                    raise ValueError(f"Row {i} error: VM IP '{identifier_value}' already exists.")
                if model_name == 'hosts' and identifier_value in existing_hosts_info:
                    raise ValueError(f"Row {i} error: Host Info '{identifier_value}' already exists.")

            missing_values = [label for label in required_labels if not row.get(label)]
            if missing_values:
                raise ValueError(f'Row {i} error: Missing values for required fields: {", ".join(missing_values)}')
            
            if model_name == 'vms':
                vm_ip_label = 'IP ADDRESS'
                host_info_label = 'HOST INFO'
                status_label = 'STATUS'

                ip_value = row.get(vm_ip_label)
                if ip_value and not is_valid_ipv4(ip_value):
                    raise ValueError(f'Row {i} error: Invalid IP address format: "{ip_value}"')
                
                host_info_value = row.get(host_info_label)
                if host_info_value:
                    if host_info_value not in existing_hosts:
                        raise ValueError(f'Row {i} error: Host "{host_info_value}" does not exist.')
                    host_id = existing_hosts[host_info_value]
                
                status_value = row.get(status_label)
                status_field_config = next((f for f in form_fields if f['name'] == 'status'), None)
                if status_value and status_field_config and status_value not in status_field_config.get('options', []):
                    allowed = status_field_config.get('options', [])
                    raise ValueError(f'Row {i} error: Invalid value "{status_value}" for field "{status_label}". Allowed values are: {allowed}.')

            elif model_name == 'hosts':
                status_label = 'STATUS'
                virt_type_label = 'TYPE'

                status_value = row.get(status_label)
                status_field_config = next((f for f in form_fields if f['name'] == 'status'), None)
                if status_value and status_field_config and status_value not in status_field_config.get('options', []):
                    allowed = status_field_config.get('options', [])
                    raise ValueError(f'Row {i} error: Invalid value "{status_value}" for field "{status_label}". Allowed values are: {allowed}.')
                
                virt_type_value = row.get(virt_type_label)
                virt_field_config = next((f for f in form_fields if f['name'] == 'virtualization_type'), None)
                if virt_type_value and virt_field_config and virt_type_value.lower() not in virt_field_config.get('options', []):
                    allowed = virt_field_config.get('options', [])
                    raise ValueError(f'Row {i} error: Invalid value "{virt_type_value}" for field "{virt_type_label}". Allowed values are: {", ".join(allowed)}.')

            item_data = {}
            for label, val in row.items():
                if label in label_to_name_map:
                    field_name = label_to_name_map[label]
                    if field_name == 'host_id' and label == host_info_label:
                        item_data[field_name] = host_id
                    else:
                        item_data[field_name] = val
            
            beijing_tz = pytz.timezone('Asia/Shanghai')
            now = datetime.now(beijing_tz)
            if hasattr(model, 'created_at'):
                item_data['created_at'] = now
            if hasattr(model, 'updated_at'):
                item_data['updated_at'] = now
            
            new_item = model(**item_data)
            db.session.add(new_item)
            
            try:
                db.session.flush()  # 暂存到数据库缓冲区，未提交
            except Exception as flush_error:
                db.session.rollback()
                if 'Duplicate entry' in str(flush_error):
                    error_msg = str(flush_error)
                    log_change('imported', model_name, 'unknown', status='failed', detail_obj={'error': error_msg, 'data': item_data})
                    raise ValueError(f'Row {i} error: Data already exists in database. {error_msg}')
                else:
                    log_change('imported', model_name, 'unknown', status='failed', detail_obj={'error': str(flush_error), 'data': item_data})
                    raise
            
            if unique_field_label and row.get(unique_field_label):
                if model_name == 'vms':
                    existing_vms_ips.add(row[unique_field_label])
                elif model_name == 'hosts':
                    existing_hosts_info.add(row[unique_field_label])

            # 准备日志数据（暂存，不立即记录）
            log_item_data = item_data.copy()
            if model_name == 'vms' and 'host_id' in log_item_data:
                host = Host.query.get(log_item_data['host_id'])
                if host:
                    log_item_data['host_info'] = host.host_info
            
            if model_name == 'hosts':
                identifier = getattr(new_item, 'host_info', str(new_item.id))
            elif model_name == 'vms':
                identifier = getattr(new_item, 'vm_ip', str(new_item.id))
            else:
                identifier = str(new_item.id)
            
            # 暂存日志信息，待提交后记录
            success_logs.append({
                'action': 'imported',
                'model_name': model_name,
                'identifier': identifier,
                'detail_obj': log_item_data
            })

        # 所有行处理完成，提交事务
        db.session.commit()
        
        # 事务提交成功后，批量记录成功日志
        for log in success_logs:
            log_change(
                log['action'],
                log['model_name'],
                log['identifier'],
                detail_obj=log['detail_obj']
            )
        
        return jsonify({
            'success': True, 
            'message': f'Successfully imported {len(csv_data)} records.'
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        log_change('imported', model_name, file.filename, status='failed', detail_obj={'error': str(e)})
        current_app.logger.error(f"Error importing data: {str(e)}", exc_info=True)
        return jsonify({'error': f'Unknown error: {str(e)}'}), 500


@generic_crud_bp.route('/<model_name>/export-csv')
@login_required
@require_model
def export_csv_view(config, model_name):
    user_id = session.get('_user_id')
    user_settings = get_user_table_settings(user_id, model_name) 
    user_visible_columns = user_settings.get('visible_columns')
    
    visible_columns_str = request.args.get('visible_columns')
    if visible_columns_str:
        visible_columns = visible_columns_str.split(',')
    elif user_visible_columns:
        visible_columns = user_visible_columns
    else:
        visible_columns = config['default_columns']
    
    valid_columns = [f['db_field'] for f in config['field_config']]
    visible_columns = [col for col in visible_columns if col in valid_columns]
    if not visible_columns:
        visible_columns = config['default_columns']
    
    visible_fields = [f for f in config['field_config'] if f['db_field'] in visible_columns]
    visible_fields.sort(key=lambda x: visible_columns.index(x['db_field']))
    
    query_data = get_query_data(config, include_pagination=False)
    items = query_data['items']
    
    si = io.StringIO()
    si.write('\ufeff')
    writer = csv.writer(si)
    
    header_row = [field['label'] for field in visible_fields]
    writer.writerow(header_row)
    
    # 预加载所有主机信息以提高性能
    host_map = {}
    if model_name == 'vms':
        host_ids = [getattr(item, 'host_id', None) for item in items if getattr(item, 'host_id', None)]
        if host_ids:
            hosts = Host.query.filter(Host.id.in_(host_ids)).all()
            host_map = {host.id: host.host_info for host in hosts}
    
    for item in items:
        row = []
        for field in visible_fields:
            # 特殊处理host_id字段，显示host_info而不是host_id
            if model_name == 'vms' and field['db_field'] == 'host_id':
                host_id = getattr(item, 'host_id', None)
                if host_id and host_id in host_map:
                    value = host_map[host_id]
                else:
                    value = host_id if host_id else ''
            else:
                value = getattr(item, field['db_field'])
            
            if isinstance(value, datetime):
                value = value.strftime('%Y-%m-%d %H:%M:%S')
            elif value is None:
                value = ''
            row.append(value)
        writer.writerow(row)
    
    output = si.getvalue()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{model_name}_{timestamp}.csv"
    
    response = Response(
        output,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )
    
    return response


@generic_crud_bp.route('/<model_name>/reset-password', methods=['POST'])
@login_required
@require_model
def reset_user_password(config, model_name):
    user_id = request.form.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('generic_crud.list_view', model_name=model_name))
        
    user.temp_password = os.getenv('TEMP_PASSWORD')
    user.password_hash = None
    user.must_change_password = True

    log_change('updated', 'users', user.username, detail_obj={'field': 'password', 'action': 'reset'})

    db.session.commit()
    
    flash(f'Password for user {user.username} has been successfully reset. You must change your password at next login.', 'success')
    return redirect(url_for('generic_crud.list_view', model_name=model_name))