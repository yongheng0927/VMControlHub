# VM Control Hub

VM Control Hub是一个用于管理虚拟机的Web应用程序，基于Flask框架开发。

## 功能特点

- 虚拟机电源控制
- 用户认证与授权
- 虚拟机管理
- 宿主机管理
- 操作日志记录
- 变更历史跟踪

## 使用说明

### 克隆项目到本地

要将项目克隆到本地，请执行以下命令：

```bash
git clone <repository-url>
cd VMControlHub
```

### 本地部署环境搭建

1. 确保已安装Docker

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

1. 构建容器并启动所有服务：
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

每个模型都定义了相应的字段和关系，可以根据需要进行扩展。

代码内注释和README文件持续更新中...