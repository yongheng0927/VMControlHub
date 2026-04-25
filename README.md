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
- 自定义字段支持：用户可以根据需要添加自定义字段，用于存储额外的信息。
- Sync功能：/vms页面，可以手动同步虚拟机的状态，保持数据的实时性。

## 项目所用底层基础镜像

- 数据库 mysql:8.4.8
- 应用服务器 python:3.10-slim
- 缓存服务器 valkey:9.0-alpine


## 使用说明

### 前置要求

- 已安装Docker
- 已安装Docker Compose
- 确保VM的的宿主机内的VM name包含了VM的IPv4地址，因为在VM Control Hub中，VM的名称会被解析为IP地址来进行操作启停重启获取状态等操作（例如: 192.168.255.230-xx等）

### 克隆项目到本地

要将项目克隆到本地，请执行以下命令：

```bash
git clone https://github.com/yongheng0927/VMControlHub.git
```

### SSH用户配置

1. 如果需要管理的主机内拥有相同用户，例如user01，请确保user01拥有家目录，拥有sudo qm/virsh等命令的权限，可以将`env/vmcontrolhub.env`SSH\_USER后的值替换为user01
2. 如果需要管理的主机内没有相同用户，建议使用ansible等工具创建vmcontrolhub用户，请确保vmcontrolhub用户拥有家目录，拥有sudo qm/virsh等命令的权限
3. 确保你要管理的主机里/home/SSH\_USER/.ssh/authorized\_keys内已经存在了vmcontrolhub或是user01用户的公钥

### 自定义字段介绍

1. 只有role为admin的用户才能配置自定义字段
2. 支持int,varchar,datetime,enum类型
3. 自定义字段可以在/hosts,/vms页面进行配置，包括字段名称、类型、是否必填，默认值，枚举值（如果是enum类型），字符长度（如果是varchar类型），排序顺序
4. 在/hosts,/vms页面的table settings中，可以配置自定义字段是否显示在表格中，以及显示的顺序

### 应用服务器配置文件

`env/vmcontrolhub.env`文件介绍：

-  如果修改了数据库参数，请确保在`env/mysql.env`中也修改了对应的参数：
- TEMP_PASSWORD: admin角色重置其他用户密码后，其他用户使用的临时密码
- SSH_USER: SSH宿主机时使用的用户，可以替换为被管理主机实际拥有的相同用户
- SECRET_KEY: 加密密钥，建议使用随机字符串，实际使用可以保持默认值或是自行修改
- MYSQL_DB_HOST: python程序连接mysql数据库的主机名(docker-compose.yml的mylsql容器的service name)
- MYSQL_DB_PORT: python程序连接mysql数据库的端口(默认3306)
- MYSQL_DB_USER: python程序连接mysql数据库的用户名(默认vmcontrolhub)
- MYSQL_DB_NAME: python程序连接mysql数据库的数据库名(默认vmcontrolhub)
- MYSQL_DB_PASSWORD: python程序连接mysql数据库的密码(默认vmcontrolhub)
- REDIS_HOST: python程序连接redis缓存的主机名(docker-compose.yml的redis容器的service name)
- REDIS_DB: python程序连接redis缓存的数据库索引(默认0)
- CACHE_DEFAULT_TIMEOUT: 缓存默认过期时间(单位：秒)(默认3000)
- REDIS_PASSWORD: python程序连接redis缓存的密码(默认vmcontrolhub-redis)
- REDIS_PORT: python程序连接redis缓存的端口(默认6379)
- CACHE_TTL_DICT: 字典元数据缓存过期时间(单位：秒)(默认43200)
- CACHE_TTL_OBJECT: 业务对象缓存过期时间(单位：秒)(默认1800)
- CACHE_TTL_STATS: 统计数据缓存过期时间(单位：秒)(默认300)
- DELAYED_DELETE_SECONDS: 延迟删除间隔(单位：秒)(默认0.5)


### 数据库配置
`env/mysql.env`文件中为默认配置

- MYSQL_DB_USER=初始化时创建的数据库用户
- MYSQL_DB_NAME=初始化时创建的数据库名
- MYSQL_DB_PASSWORD=初始化时创建的数据库密码
- MYSQL_DATABASE_PORT=数据库容器端口(默认3306)
- MYSQL_ROOT_PASSWORD=mysql数据库容器的root密码(默认root-mysql-vmcontrolhub)


### 部署说明

1. 启动所有服务：
   ```bash
    docker-compose up -d
    ```
2. 创建初始的超级用户
   ```bash
   docker compose exec app python /home/vmcontrolhub/manage.py createsuperuser
   ```
   输入超级用户名、密码、确认密码
3. 复制公钥到要管理的主机内的相同用户的/home/SSH\_USER/.ssh/authorized\_keys文件中
   ```bash
   docker exec vmcontrolhub-app cat /home/vmcontrolhub/.ssh/id_rsa.pub
   ```
4. 确保要管理的主机内的SSH服务已启动，并监听在默认端口22
5. 访问应用：<http://localhost:5000>，使用超级用户名、密码登录
6. 用户忘记密码？
   1. 方法1 web界面操作
      1. 使用role为admin的用户登录，在admin/users页面，点击对应用户“reset password”按钮
      2. 重置后为临时密码，需要在登录后立即修改，默认的临时密码为`env/vmcontrolhub.env`中的`TEMP_PASSWORD`，可以自行更改为其他密码
   2. 方法2 主机内命令行操作
      1. docker compose exec app python /home/vmcontrolhub/manage.py changepassword
      2. 输入用户名、新密码、确认新密码
      2. 重置后为通过加密存储的新密码，不需要在登录后立即修改
7. 修改监听在宿主机的端口
   - 修改`docker-compose.yml`文件中的app服务的`ports`参数，默认值为5000
   - 示例：
      ```yaml
      ports:
        - 8080（宿主机端口）:5000
      ```



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
2. 确认宿主机上的虚拟化服务（如 libvirt等）是否运行
3. 验证用户权限是否足够执行相关操作
4. 检查应用日志是否有相关错误提示

- 界面显示异常：

1. 清除浏览器缓存或使用无痕模式尝试
2. 确认浏览器版本，推荐使用 Chrome、Firefox 等现代浏览器最新版本

代码内注释和README文件持续更新中...