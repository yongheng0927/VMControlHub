SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

USE `vmcontrolhub`;

CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID,自增主键',
    `username` VARCHAR(100) NOT NULL UNIQUE COMMENT '登录用户名,全局唯一',
    `password_hash` VARCHAR(255) NULL COMMENT '密码哈希值,存储加密后的密码',
    `temp_password` VARCHAR(255) NULL COMMENT '临时明文密码',
    `role` ENUM('admin', 'manager', 'operator') NOT NULL DEFAULT 'operator' COMMENT '用户角色,控制权限范围',
    `must_change_password` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '密码重置标志,1表示需要强制修改密码,0表示不需要强制修改密码',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '用户创建时间',
    `last_login` DATETIME NULL COMMENT '最后登录时间',
    `password_last_changed` DATETIME NULL COMMENT '最后密码修改时间',
    `table_set` JSON NULL COMMENT '用户浏览器表格样式'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统用户表';

CREATE TABLE IF NOT EXISTS `hosts` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主机id,自增主键',
    `host_info` VARCHAR(255) NOT NULL COMMENT '主机标识,格式为"ipv4_hostname"',
    `virtualization_type` ENUM('kvm', 'pve', 'other') NOT NULL COMMENT '虚拟化类型,决定管理方式',
    `department` VARCHAR(100) NOT NULL COMMENT '所属部门,用于权限和统计',
    `status` ENUM('running', 'stopped', 'unknown') NOT NULL DEFAULT 'unknown' COMMENT '主机状态,running表示运行中,stopped表示已停止,unknown表示未知',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间,自动维护',
    `vm_count` INT NOT NULL DEFAULT 0 COMMENT '宿主机关联的VM数量',
    UNIQUE INDEX `idx_hosts_host_info` (`host_info`) COMMENT '主机标识唯一索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='物理宿主机表';

CREATE TABLE IF NOT EXISTS `vms` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '虚拟机id,自增主键',
    `vm_ip` VARCHAR(15) NOT NULL COMMENT '虚拟机IP地址',
    `cpus` INT NULL COMMENT 'cpu数量',
    `memory_gb` INT NULL COMMENT '内存大小(gb)',
    `disk_gb` INT NULL COMMENT '磁盘大小(gb)',
    `domain_name` VARCHAR(20) NULL COMMENT '虚拟机域名',
    `os_type` VARCHAR(100) NOT NULL COMMENT '操作系统类型',
    `vm_user` VARCHAR(100) NOT NULL COMMENT '虚拟机登录用户名',
    `host_id` INT NOT NULL COMMENT '所属宿主机ID,关联hosts表的id',
    `status` ENUM('running', 'stopped', 'unknown') NOT NULL DEFAULT 'unknown' COMMENT '虚拟机状态,running表示运行中,stopped表示已停止,unknown表示未知',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间,自动维护',
    UNIQUE INDEX `idx_vms_vm_ip` (`vm_ip`) COMMENT '虚拟机IP唯一索引',
    CONSTRAINT `fk_vms_host` FOREIGN KEY (`host_id`) REFERENCES `hosts` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='虚拟机表';

-- 添加VM操作相关的触发器,用于自动更新hosts表中的vm_count字段
DELIMITER $$

-- 插入VM后更新宿主机关联的VM数量
CREATE TRIGGER after_vm_insert
AFTER INSERT ON vms
FOR EACH ROW
BEGIN
    UPDATE hosts SET vm_count = vm_count + 1 WHERE id = NEW.host_id;
END$$

-- 删除VM后更新宿主机关联的VM数量
CREATE TRIGGER after_vm_delete
AFTER DELETE ON vms
FOR EACH ROW
BEGIN
    UPDATE hosts SET vm_count = vm_count - 1 WHERE id = OLD.host_id;
END$$

-- 更新新旧宿主机关联的VM数量
CREATE TRIGGER after_vm_update
AFTER UPDATE ON vms
FOR EACH ROW
BEGIN
    IF OLD.host_id != NEW.host_id THEN
        UPDATE hosts SET vm_count = vm_count - 1 WHERE id = OLD.host_id;
        UPDATE hosts SET vm_count = vm_count + 1 WHERE id = NEW.host_id;
    END IF;
END$$

DELIMITER ;

CREATE TABLE IF NOT EXISTS `change_logs` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID,自增主键',
    `time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    `username` VARCHAR(255) NOT NULL COMMENT '执行操作的用户名(保留历史值)',
    `action` ENUM('create', 'update', 'delete') NOT NULL COMMENT '操作类型',
    `status` ENUM('success', 'failed') NOT NULL COMMENT '操作状态',
    `object_type` ENUM('host', 'vm', 'user') NOT NULL COMMENT '操作对象类型',
    `object_identifier` VARCHAR(255) NOT NULL COMMENT '操作对象唯一标识(如VM IP,Host info,Username)',
    `detail` JSON NOT NULL COMMENT '操作详情'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据变更日志表';

CREATE TABLE IF NOT EXISTS `operation_logs` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID,自增主键',
    `time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    `username` VARCHAR(255) NOT NULL COMMENT '执行操作的用户名(保留历史值)',
    `vm_ip` VARCHAR(15) NOT NULL COMMENT '操作的虚拟机IP(保留历史值)',
    `action` ENUM('start', 'shutdown', 'reboot') NOT NULL COMMENT '操作类型',
    `status` ENUM('success', 'failed') NOT NULL COMMENT '操作状态',
    `details` JSON NULL COMMENT '操作详情或错误信息'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='虚拟机操作日志表';

-- 自定义字段配置表
CREATE TABLE IF NOT EXISTS `custom_fields` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '字段唯一主键ID',
  `resource_type` VARCHAR(16) NOT NULL COMMENT '资源类型,仅允许host/vm,host=宿主机,vm=虚拟机',
  `field_name` VARCHAR(255) NOT NULL COMMENT '字段前端显示名称,支持用户重命名',
  `field_type` VARCHAR(16) NOT NULL COMMENT '字段数据类型,仅允许int/varchar/datetime/enum',
  `field_length` INT NULL DEFAULT 255 COMMENT '字段长度限制,仅varchar类型生效',
  `is_required` TINYINT NOT NULL DEFAULT 0 COMMENT '是否必填,1=必填,0=选填',
  `default_value` VARCHAR(255) NULL COMMENT '字段默认值,按field_type对应类型解析',
  `sort` INT NOT NULL DEFAULT 0 COMMENT '前端表单/列表的展示排序,数字越小越靠前',
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '字段创建时间',
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '字段最后更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_resource_type` (`resource_type`) COMMENT '资源类型查询索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自定义字段配置表';

-- 自定义字段枚举选项表
CREATE TABLE IF NOT EXISTS `custom_field_enum_options` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '枚举选项唯一主键ID',
  `field_id` INT NOT NULL COMMENT '关联custom_fields表的主键id,仅关联field_type=enum的字段',
  `option_key` VARCHAR(255) NOT NULL COMMENT '枚举选项存储值,创建后不可修改',
  `option_label` VARCHAR(255) NOT NULL COMMENT '枚举选项前端显示名称,支持修改',
  `sort` INT NOT NULL DEFAULT 0 COMMENT '下拉选项展示排序,数字越小越靠前',
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '选项创建时间',
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '选项最后更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_field_option_key` (`field_id`, `option_key`) COMMENT '同字段下option_key唯一',
  INDEX `idx_field_id` (`field_id`) COMMENT '字段ID查询索引',
  CONSTRAINT `fk_enum_field_id` FOREIGN KEY (`field_id`) REFERENCES `custom_fields` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自定义字段枚举选项表';

-- 自定义字段值表
CREATE TABLE IF NOT EXISTS `custom_field_values` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '值记录唯一主键ID',
  `field_id` INT NOT NULL COMMENT '关联custom_fields表的主键id',
  `resource_type` VARCHAR(16) NOT NULL COMMENT '资源类型,host=宿主机,vm=虚拟机,和关联字段配置保持一致',
  `resource_id` INT NOT NULL COMMENT '关联的宿主机ID(hosts.id)或虚拟机ID(vms.id)',
  `int_value` BIGINT NULL COMMENT '存储int类型的字段值',
  `varchar_value` VARCHAR(255) NULL COMMENT '存储varchar类型的字段值',
  `datetime_value` DATETIME NULL COMMENT '存储datetime类型的字段值',
  `enum_value` VARCHAR(255) NULL COMMENT '存储enum类型的字段值,对应枚举选项的option_key',
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '值最后更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_field_resource` (`field_id`, `resource_id`) COMMENT '一个资源的一个字段仅存一条值',
  INDEX `idx_resource` (`resource_type`, `resource_id`) COMMENT '资源类型+资源ID联合查询索引',
  CONSTRAINT `fk_value_field_id` FOREIGN KEY (`field_id`) REFERENCES `custom_fields` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自定义字段值表';