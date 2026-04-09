from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
from app.models import db, CustomField, CustomFieldEnumOption, CustomFieldValue
from app.services.permission_service import admin_required
from app.services.log_service import log_change, to_dict
from datetime import datetime

custom_fields_bp = Blueprint('custom_fields', __name__, url_prefix='/')


def field_to_dict(field):
    """将CustomField对象转换为字典，包含枚举选项"""
    field_dict = {
        'id': field.id,
        'resource_type': field.resource_type,
        'field_name': field.field_name,
        'field_type': field.field_type,
        'field_length': field.field_length,
        'is_required': field.is_required,
        'default_value': field.default_value,
        'sort': field.sort,
        'create_time': field.create_time.isoformat() if field.create_time else None,
        'update_time': field.update_time.isoformat() if field.update_time else None
    }
    
    if field.field_type == 'enum':
        enum_options = field.enum_options.order_by(CustomFieldEnumOption.sort).all()
        field_dict['enum_options'] = [
            {
                'id': opt.id,
                'option_key': opt.option_key,
                'option_label': opt.option_label,
                'sort': opt.sort
            } for opt in enum_options
        ]
    
    return field_dict


def validate_field_type(field_type):
    """验证字段类型是否合法"""
    return field_type in ['int', 'varchar', 'datetime', 'enum']


def get_custom_fields(resource_type):
    """获取指定资源类型的有效自定义字段"""
    fields = CustomField.query.filter_by(
        resource_type=resource_type
    ).order_by(CustomField.sort).all()
    return [field_to_dict(field) for field in fields]


# 宿主机自定义字段接口
@custom_fields_bp.route('/api/hosts/custom-fields', methods=['GET'])
@login_required
def get_host_custom_fields():
    try:
        fields = get_custom_fields('host')
        return jsonify({
            'success': True,
            'data': fields
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Failed to get custom fields: {str(e)}'
        }), 500


@custom_fields_bp.route('/api/hosts/custom-fields', methods=['POST'])
@login_required
@admin_required
def create_host_custom_field():
    try:
        data = request.get_json() or {}
        
        field_name = data.get('field_name', '').strip()
        field_type = data.get('field_type', '').strip()
        field_length = data.get('field_length', 255)
        is_required = data.get('is_required', 0)
        default_value = data.get('default_value')
        sort = data.get('sort', 0)
        enum_options = data.get('enum_options', [])
        
        if not field_name or not field_type:
            return jsonify({
                'success': False,
                'message': 'field_name and field_type are required'
            }), 400
        
        if not validate_field_type(field_type):
            return jsonify({
                'success': False,
                'message': 'Invalid field_type, must be one of: int, varchar, datetime, enum'
            }), 400
        
        existing_field = CustomField.query.filter_by(
            resource_type='host',
            field_name=field_name
        ).first()
        
        if existing_field:
            return jsonify({
                'success': False,
                'message': f'Field with name "{field_name}" already exists'
            }), 400
        
        new_field = CustomField(
            resource_type='host',
            field_name=field_name,
            field_type=field_type,
            field_length=field_length,
            is_required=is_required,
            default_value=default_value,
            sort=sort
        )
        
        db.session.add(new_field)
        db.session.flush()
        
        if field_type == 'enum' and enum_options:
            for opt in enum_options:
                opt_key = opt.get('option_key', '').strip()
                opt_label = opt.get('option_label', '').strip()
                opt_sort = opt.get('sort', 0)
                if opt_label:
                    if not opt_key:
                        opt_key = opt_label
                    enum_opt = CustomFieldEnumOption(
                        field_id=new_field.id,
                        option_key=opt_key,
                        option_label=opt_label,
                        sort=opt_sort
                    )
                    db.session.add(enum_opt)
        
        db.session.commit()
        
        log_change('created', 'host', field_name, detail_obj=to_dict(new_field))
        
        return jsonify({
            'success': True,
            'message': 'Custom field created successfully',
            'data': field_to_dict(new_field)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to create custom field: {str(e)}'
        }), 500


@custom_fields_bp.route('/api/hosts/custom-fields/<int:field_id>', methods=['PUT'])
@login_required
@admin_required
def update_host_custom_field(field_id):
    try:
        field = CustomField.query.get(field_id)
        if not field:
            return jsonify({
                'success': False,
                'message': 'Field not found'
            }), 404
        
        if field.resource_type != 'host':
            return jsonify({
                'success': False,
                'message': 'Permission denied'
            }), 403
        
        data = request.get_json() or {}
        
        old_data = to_dict(field)
        
        if 'field_name' in data:
            new_field_name = data['field_name'].strip()
            if new_field_name != field.field_name:
                existing_field = CustomField.query.filter_by(
                    resource_type='host',
                    field_name=new_field_name
                ).first()
                if existing_field and existing_field.id != field_id:
                    return jsonify({
                        'success': False,
                        'message': f'Field with name "{new_field_name}" already exists'
                    }), 400
            field.field_name = new_field_name
        if 'field_length' in data:
            field.field_length = data['field_length']
        if 'is_required' in data:
            field.is_required = data['is_required']
        if 'default_value' in data:
            field.default_value = data['default_value']
        if 'sort' in data:
            field.sort = data['sort']
        
        if 'enum_options' in data and field.field_type == 'enum':
            enum_options = data['enum_options']
            existing_opts = {opt.option_key: opt for opt in field.enum_options.all()}
            
            for opt in enum_options:
                opt_key = opt.get('option_key', '').strip()
                opt_label = opt.get('option_label', '').strip()
                opt_sort = opt.get('sort', 0)
                if not opt_label:
                    continue
                
                if opt_key and opt_key in existing_opts:
                    existing_opt = existing_opts.pop(opt_key)
                    existing_opt.option_label = opt_label
                    existing_opt.sort = opt_sort
                else:
                    if not opt_key:
                        opt_key = opt_label
                    new_opt = CustomFieldEnumOption(
                        field_id=field_id,
                        option_key=opt_key,
                        option_label=opt_label,
                        sort=opt_sort
                    )
                    db.session.add(new_opt)
            
            for remaining_opt in existing_opts.values():
                db.session.delete(remaining_opt)
        
        db.session.commit()
        
        log_change('update', 'host', field.field_name, detail_obj={'old': old_data, 'new': to_dict(field)})
        
        return jsonify({
            'success': True,
            'message': 'Custom field updated successfully',
            'data': field_to_dict(field)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to update custom field: {str(e)}'
        }), 500


@custom_fields_bp.route('/api/hosts/custom-fields/<int:field_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_host_custom_field(field_id):
    try:
        field = CustomField.query.get(field_id)
        if not field:
            return jsonify({
                'success': False,
                'message': 'Field not found'
            }), 404
        
        if field.resource_type != 'host':
            return jsonify({
                'success': False,
                'message': 'Permission denied'
            }), 403
        
        old_data = to_dict(field)
        
        # 物理删除字段（级联删除会自动删除关联的枚举选项和值）
        db.session.delete(field)
        db.session.commit()
        
        log_change('delete', 'host', field.field_name, detail_obj=old_data)
        
        return jsonify({
            'success': True,
            'message': 'Custom field deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to delete custom field: {str(e)}'
        }), 500


# 虚拟机自定义字段接口
@custom_fields_bp.route('/api/vms/custom-fields', methods=['GET'])
@login_required
def get_vm_custom_fields():
    try:
        fields = get_custom_fields('vm')
        return jsonify({
            'success': True,
            'data': fields
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Failed to get custom fields: {str(e)}'
        }), 500


@custom_fields_bp.route('/api/vms/custom-fields', methods=['POST'])
@login_required
@admin_required
def create_vm_custom_field():
    try:
        data = request.get_json() or {}
        
        field_name = data.get('field_name', '').strip()
        field_type = data.get('field_type', '').strip()
        field_length = data.get('field_length', 255)
        is_required = data.get('is_required', 0)
        default_value = data.get('default_value')
        sort = data.get('sort', 0)
        enum_options = data.get('enum_options', [])
        
        if not field_name or not field_type:
            return jsonify({
                'success': False,
                'message': 'field_name and field_type are required'
            }), 400
        
        if not validate_field_type(field_type):
            return jsonify({
                'success': False,
                'message': 'Invalid field_type, must be one of: int, varchar, datetime, enum'
            }), 400
        
        existing_field = CustomField.query.filter_by(
            resource_type='vm',
            field_name=field_name
        ).first()
        
        if existing_field:
            return jsonify({
                'success': False,
                'message': f'Field with name "{field_name}" already exists'
            }), 400
        
        new_field = CustomField(
            resource_type='vm',
            field_name=field_name,
            field_type=field_type,
            field_length=field_length,
            is_required=is_required,
            default_value=default_value,
            sort=sort
        )
        
        db.session.add(new_field)
        db.session.flush()
        
        if field_type == 'enum' and enum_options:
            for opt in enum_options:
                opt_key = opt.get('option_key', '').strip()
                opt_label = opt.get('option_label', '').strip()
                opt_sort = opt.get('sort', 0)
                if opt_label:
                    if not opt_key:
                        opt_key = opt_label
                    enum_opt = CustomFieldEnumOption(
                        field_id=new_field.id,
                        option_key=opt_key,
                        option_label=opt_label,
                        sort=opt_sort
                    )
                    db.session.add(enum_opt)
        
        db.session.commit()
        
        log_change('create', 'vm', field_name, detail_obj=to_dict(new_field))
        
        return jsonify({
            'success': True,
            'message': 'Custom field created successfully',
            'data': field_to_dict(new_field)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to create custom field: {str(e)}'
        }), 500


@custom_fields_bp.route('/api/vms/custom-fields/<int:field_id>', methods=['PUT'])
@login_required
@admin_required
def update_vm_custom_field(field_id):
    try:
        field = CustomField.query.get(field_id)
        if not field:
            return jsonify({
                'success': False,
                'message': 'Field not found'
            }), 404
        
        if field.resource_type != 'vm':
            return jsonify({
                'success': False,
                'message': 'Permission denied'
            }), 403
        
        data = request.get_json() or {}
        
        old_data = to_dict(field)
        
        if 'field_name' in data:
            new_field_name = data['field_name'].strip()
            if new_field_name != field.field_name:
                existing_field = CustomField.query.filter_by(
                    resource_type='vm',
                    field_name=new_field_name
                ).first()
                if existing_field and existing_field.id != field_id:
                    return jsonify({
                        'success': False,
                        'message': f'Field with name "{new_field_name}" already exists'
                    }), 400
            field.field_name = new_field_name
        if 'field_length' in data:
            field.field_length = data['field_length']
        if 'is_required' in data:
            field.is_required = data['is_required']
        if 'default_value' in data:
            field.default_value = data['default_value']
        if 'sort' in data:
            field.sort = data['sort']
        
        if 'enum_options' in data and field.field_type == 'enum':
            enum_options = data['enum_options']
            existing_opts = {opt.option_key: opt for opt in field.enum_options.all()}
            
            for opt in enum_options:
                opt_key = opt.get('option_key', '').strip()
                opt_label = opt.get('option_label', '').strip()
                opt_sort = opt.get('sort', 0)
                if not opt_label:
                    continue
                
                if opt_key and opt_key in existing_opts:
                    existing_opt = existing_opts.pop(opt_key)
                    existing_opt.option_label = opt_label
                    existing_opt.sort = opt_sort
                else:
                    if not opt_key:
                        opt_key = opt_label
                    new_opt = CustomFieldEnumOption(
                        field_id=field_id,
                        option_key=opt_key,
                        option_label=opt_label,
                        sort=opt_sort
                    )
                    db.session.add(new_opt)
            
            for remaining_opt in existing_opts.values():
                db.session.delete(remaining_opt)
        
        db.session.commit()
        
        log_change('update', 'vm', field.field_name, detail_obj={'old': old_data, 'new': to_dict(field)})
        
        return jsonify({
            'success': True,
            'message': 'Custom field updated successfully',
            'data': field_to_dict(field)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to update custom field: {str(e)}'
        }), 500


@custom_fields_bp.route('/api/vms/custom-fields/<int:field_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_vm_custom_field(field_id):
    try:
        field = CustomField.query.get(field_id)
        if not field:
            return jsonify({
                'success': False,
                'message': 'Field not found'
            }), 404
        
        if field.resource_type != 'vm':
            return jsonify({
                'success': False,
                'message': 'Permission denied'
            }), 403
        
        old_data = to_dict(field)
        
        # 物理删除字段（级联删除会自动删除关联的枚举选项和值）
        db.session.delete(field)
        db.session.commit()
        
        log_change('delete', 'vm', field.field_name, detail_obj=old_data)
        
        return jsonify({
            'success': True,
            'message': 'Custom field deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to delete custom field: {str(e)}'
        }), 500


# 获取资源的自定义字段值
@custom_fields_bp.route('/api/hosts/<int:resource_id>/custom-field-values', methods=['GET'])
@login_required
def get_host_custom_field_values(resource_id):
    try:
        values = CustomFieldValue.query.filter_by(
            resource_type='host',
            resource_id=resource_id
        ).all()
        
        result = {}
        for val in values:
            field = val.field
            if not field:
                continue
            
            if field.field_type == 'int':
                result[str(field.id)] = val.int_value
            elif field.field_type == 'varchar':
                result[str(field.id)] = val.varchar_value
            elif field.field_type == 'datetime':
                result[str(field.id)] = val.datetime_value.isoformat() if val.datetime_value else None
            elif field.field_type == 'enum':
                result[str(field.id)] = val.enum_value
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Failed to get custom field values: {str(e)}'
        }), 500


@custom_fields_bp.route('/api/vms/<int:resource_id>/custom-field-values', methods=['GET'])
@login_required
def get_vm_custom_field_values(resource_id):
    try:
        values = CustomFieldValue.query.filter_by(
            resource_type='vm',
            resource_id=resource_id
        ).all()
        
        result = {}
        for val in values:
            field = val.field
            if not field:
                continue
            
            if field.field_type == 'int':
                result[str(field.id)] = val.int_value
            elif field.field_type == 'varchar':
                result[str(field.id)] = val.varchar_value
            elif field.field_type == 'datetime':
                result[str(field.id)] = val.datetime_value.isoformat() if val.datetime_value else None
            elif field.field_type == 'enum':
                result[str(field.id)] = val.enum_value
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Failed to get custom field values: {str(e)}'
        }), 500
