# VM Control Hub

VM Control Hub是一个用于管理虚拟机的Web应用程序，基于Flask框架开发。

## 功能特点

- 用户认证与授权管理
- 宿主机管理
- 虚拟机管理
- 详细的操作日志记录与审计
- 变更历史跟踪与回溯
- 批量操作支持（批量编辑、删除等）
- 数据导入导出功能
- 交互反馈：操作后显示通知提示，提供清晰的操作结果反馈
- 表格优化：支持超紧凑表格显示、列搜索与配置，提升数据浏览效率

## 使用说明

### 克隆项目到本地

要将项目克隆到本地，请执行以下命令：
```bash
git clone <repository-url>
cd VMControlHub
```
### 本地部署环境搭建

1. 确保已安装Docker
2. 检查系统时间与时区设置，建议统一使用 Asia/Shanghai 时区

### 配置SSH agent
1. 如果需要管理的主机内拥有相同用户,例如user01,请确保user01拥有家目录,拥有sudo qm/virsh等命令的权限,可以将`.env`SSH_USER后的值替换为user01
2. 如果需要管理的主机内没有相同用户,建议使用ansible等工具创建vmcontrolhub用户,请确保vmcontrol用户拥有家目录,拥有sudo qm/virsh等命令的权限
3. 确保你要管理的主机里/home/SSH_USER/.ssh/authorized_keys内已经存在了vmcontrol的公钥
4. 确保本地部署环境中的/home/vmcontrolhub/.ssh/known_hosts已经存在了所有要管理主机的公钥
5. ```bash
   sh setup_ssh_agent_container.sh
   ```

### 添加数据库字段

要在现有模型中添加新的数据库字段，请按以下步骤操作：

1. 在`conf/mysql-init.sql`中添加到对应的数据表中
2. 在`app/models.py`中找到对应的模型类（如`VM`、`Host`等）
3. 添加新的字段定义，例如：
   ```python
   new_field = db.Column(db.String(100), nullable=True, comment='新字段说明')
   ```
4. 如果是添加到现有表中，需要创建数据库迁移脚本或手动更新数据库表结构
5. 如果需要在前端后端处理该字段，请相应地更新`generic_crud.py`中对应的模型的配置

### 使用Docker部署

 构建容器并启动所有服务：
   ```bash
   docker-compose up -d --build
   ```
2. 访问应用：http://localhost:5000

### 数据库模型说明

项目包含以下主要数据模型：

- `User`：用户模型，用于用户认证和权限管理
- `Host`：宿主机模型，包含宿主机信息
- `VM`：虚拟机模型，包含虚拟机信息及其与宿主机的关联
- `ChangeLog`：变更日志模型，记录数据变更历史
- `OperationLog`：操作日志模型，记录虚拟机操作日志

### 常见问题
- 无法连接到远程主机：
1. 检查 SSH 密钥配置是否正确
2. 确认网络连通性和防火墙设置
3. 查看ssh-agent-container服务是否正常运行
- 应用启动失败：
1. 检查数据库服务是否正常
2. 查看应用日志排查错误原因
3. 确认环境变量配置正确
- 虚拟机操作无响应：
1. 检查宿主机状态是否正常
2. 确认宿主机上的虚拟化服务（如 libvirt、Proxmox 等）是否运行
3. 验证用户权限是否足够执行相关操作
- 界面显示异常：
1. 清除浏览器缓存或使用无痕模式尝试
2. 确认浏览器版本，推荐使用 Chrome、Firefox 等现代浏览器最新版本

每个模型都定义了相应的字段和关系，可以根据需要进行扩展。

代码内注释和README文件持续更新中...