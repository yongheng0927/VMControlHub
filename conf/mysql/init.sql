-- 设置全局字符集和排序规则
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

CREATE DATABASE IF NOT EXISTS `vmcontrolhub` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `vmcontrolhub`;

CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID,自增主键',
    `username` VARCHAR(100) NOT NULL UNIQUE COMMENT '登录用户名,全局唯一',
    `password_hash` VARCHAR(255) NULL COMMENT '密码哈希值,存储加密后的密码',
    `temp_password` VARCHAR(255) NULL COMMENT '临时明文密码',
    `role` ENUM('admin', 'manager', 'operator') NOT NULL DEFAULT 'operator' COMMENT '用户角色,控制权限范围',
    `must_change_password` BOOLEAN NOT NULL DEFAULT TRUE COMMENT '密码重置标志,首次登录强制修改密码(admin默认开启)',
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
    `status` ENUM('active', 'inactive') NOT NULL DEFAULT 'active' COMMENT '主机状态,active表示可用,inactive表示不可用',
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
    `status` ENUM('active', 'inactive') NOT NULL DEFAULT 'active' COMMENT '虚拟机状态,active表示可用,inactive表示不可用',
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
    `vm_ip` VARCHAR(15) NOT NULL COMMENT '操作的虚拟机IP(保留历史值)',  -- 即使VM删除也保留IP
    `action` ENUM('start', 'shutdown', 'reboot') NOT NULL COMMENT '操作类型',
    `status` ENUM('success', 'failed') NOT NULL COMMENT '操作状态',
    `details` JSON NULL COMMENT '操作详情或错误信息'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='虚拟机操作日志表';


-- 插入默认管理员用户 - 使用明文密码admin,初次登录后必须修改
INSERT INTO `users` (`username`, `temp_password`, `role`, `must_change_password`, `password_last_changed`)
VALUES ('admin', 'admin', 'admin', TRUE, NULL);


-- 创建应用用户并分配所有权限
CREATE USER IF NOT EXISTS 'mysql_user'@'%' IDENTIFIED BY '123456';
GRANT ALL PRIVILEGES ON `vmcontrolhub`.* TO 'mysql_user'@'%';
FLUSH PRIVILEGES;