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
- 后端 python:3.10-slim
- 前端 nginx:1.24-alpine

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
### 修改nginx在宿主机的端口

1. 在执行docker-compose up -d命令前，先执行以下命令：
2. 打开`.env`文件
3. 找到`NGINX_HOST_PORT`项
4. 将其值修改为8080，例如：`NGINX_HOST_PORT=8080`
5. 保存文件

### SSH用户配置

1. 如果需要管理的主机内拥有相同用户，例如user01，请确保user01拥有家目录，拥有sudo qm/virsh等命令的权限，可以将`.env`SSH\_USER后的值替换为user01
2. 如果需要管理的主机内没有相同用户，建议使用ansible等工具创建vmcontrolhub用户，请确保vmcontrolhub用户拥有家目录，拥有sudo qm/virsh等命令的权限
3. 确保你要管理的主机里/home/SSH\_USER/.ssh/authorized\_keys内已经存在了vmcontrolhub或是user01用户的公钥

### 自定义字段介绍

1. 只有role为admin的用户才能配置自定义字段
2. 支持int,varchar,datetime,enum类型
3. 自定义字段可以在/hosts,/vms页面进行配置，包括字段名称、类型、是否必填，默认值，枚举值（如果是enum类型），字符长度（如果是varchar类型），排序顺序
4. 在/hosts,/vms页面的table settings中，可以配置自定义字段是否显示在表格中，以及显示的顺序

### 配置文件

`.env`文件中可以和建议修改的配置项

- Nginx宿主机端口（默认80）
- admin角色重置其他用户密码后，其他用户的临时密码
- SSH宿主机时使用的用户，可以替换为被管理主机实际拥有的相同用户
- 加密密钥，建议使用随机字符串，实际使用时请更改为安全的密码
- python程序连接mysql数据库的主机名(docker-compose.yml的mylsql容器的service name)

### 使用Docker部署

1. 构建容器并启动所有服务：

```bash
docker-compose up -d
```

1. 访问应用：<http://localhost>
2. 初始默认账号密码为：admin/admin
3. 复制公钥到要管理的主机内的相同用户的/home/SSH\_USER/.ssh/authorized\_keys文件中
   ```bash
   docker exec vmcontrolhub-app cat /home/vmcontrolhub/.ssh/id_rsa.pub 
   ```
4. 确保要管理的主机内的SSH服务已启动，并监听在默认端口22

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
