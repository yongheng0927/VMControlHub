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

### 前置要求

- 已安装Docker
- 已安装Docker Compose
- 确保VM的的宿主机内的VM name包含了VM的IPv4地址，因为在VM Control Hub中，VM的名称会被解析为IP地址来进行操作启停重启

### 克隆项目到本地

要将项目克隆到本地，请执行以下命令：
```bash
git clone https://github.com/yongheng0927/VMControlHub.git
cd VMControlHub
```
### 本地部署环境搭建

1. 确保已安装Docker
2. 检查系统时间与时区设置，建议统一使用 Asia/Shanghai 时区

### 配置SSH agent
1. 如果需要管理的主机内拥有相同用户，例如user01，请确保user01拥有家目录，拥有sudo qm/virsh等命令的权限，可以将`.env`SSH_USER后的值替换为user01
2. 如果需要管理的主机内没有相同用户，建议使用ansible等工具创建vmcontrolhub用户，请确保vmcontrolhub用户拥有家目录，拥有sudo qm/virsh等命令的权限
3. 确保你要管理的主机里/home/SSH_USER/.ssh/authorized_keys内已经存在了vmcontrolhub或是user01用户的公钥

### 添加数据库字段

要在现有模型中添加新的数据库字段，请按以下步骤操作：

1. 在`conf/mysql/init.sql`中添加到对应的数据表中
2. 在`app/models.py`中找到对应的模型类（如`VM`、`Host`等）
3. 添加新的字段定义，例如：
   ```python
   new_field = db.Column(db.String(100)， nullable=True， comment='新字段说明')
   ```
4. 如果是添加到现有表中，需要创建数据库迁移脚本或手动更新数据库表结构
5. 如果需要在前端后端处理该字段，请相应地更新`generic_crud.py`中对应的模型的配置

### 使用Docker部署

 1. 构建容器并启动所有服务：
   ```bash
   docker-compose up -d --build
   ```
2. 访问应用：http://localhost:5000
3. 初始默认账号密码为：admin/admin（可以在`conf/mysql/init.sql`中修改）
4. docker exec -it vmcontrolhub-app cat /home/vmcontrolhub/.ssh/id_rsa.pub (复制公钥到要管理的主机内的authorized_keys)
5. 确保要管理的主机内的SSH服务已启动，并监听在默认端口22

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

- 应用启动失败：
1. 检查数据库服务是否正常
2. 查看应用日志排查错误原因
3. 确认环境变量配置正确

- 虚拟机操作无响应：
1. 检查宿主机状态是否正常
2. 确认宿主机上的虚拟化服务（如 libvirt、Proxmox 等）是否运行
3. 验证用户权限是否足够执行相关操作
4. 检查应用日志是否有相关错误提示

- 界面显示异常：
1. 清除浏览器缓存或使用无痕模式尝试
2. 确认浏览器版本，推荐使用 Chrome、Firefox 等现代浏览器最新版本

每个模型都定义了相应的字段和关系，可以根据需要进行扩展。

## 更新日志
- 2026-03-06：
1. 移除了setup_ssh_agent_container.sh脚本，将ssh agent systemd服务提供的功能内置到容器内，并在Dockerfile中添加了相关的配置，可以在容器内使用ssh agent来管理宿主机的ssh连接，避免在宿主机上配置ssh agent
2. mysql数据库改造，不再直接将init.sql文件挂载到容器内，而是在conf/mysql/中新增Dockerfile，用于直接构建vmcontrolhub项目需要的mysql镜像，镜像内包含了init.sql文件，镜像构建时就会初始化数据库，而不是在mysql容器启动时执行init.sql文件。


代码内注释和README文件持续更新中...