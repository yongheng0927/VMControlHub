# ==========================================
# VMControlHub Gunicorn 动态优化配置文件
# ==========================================

import multiprocessing
import os

# 内存池限制
os.environ["MALLOC_ARENA_MAX"] = "2"

# 1. 自动获取 CPU 核心数
cores = multiprocessing.cpu_count()

# 2. 网络绑定
# 容器内部监听 5000 端口
bind = "0.0.0.0:5000"

# 3. 动态工作进程设置 (关键优化)
# 逻辑：核心数越多，进程数越多，但上限设为 12 以节省内存
workers = max(2, min(cores, 6))

# 4. 线程设置
# 每个进程配合 8 个线程，总并发能力为 workers * threads (6 * 8 = 48)
threads = 8
worker_class = "sync"  # 针对系统命令调用（qm/pvesh）保持 sync 模式最稳妥
preload_app = True  # 使用共享内存

# 5. 核心：真实 IP 处理
# 信任来自 Docker 网络或 Nginx 代理的请求
forwarded_allow_ips = '*'
proxy_allow_ips = "*"

# 6. 日志配置
# 输出到标准输出，方便通过 `docker logs -f` 查看
accesslog = "-"
errorlog = "-"
loglevel = "info"

# 针对 Nginx 代理优化的日志格式
access_log_format = '%({X-Real-IP}i)s %({X-Forwarded-For}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# 7. 超时与性能 (针对虚拟机操作优化)
# 启动大内存 VM 可能耗时较长，设为 60 秒
timeout = 60
keepalive = 5
graceful_timeout = 30
worker_tmp_dir = "/dev/shm" # 减少磁盘IO
max_requests = 500  #  处理500~600个请求后worker自动重启
max_requests_jitter = 100


# 8. 进程管理
proc_name = "vmcontrolhub_app"
daemon = False  # Docker 模式必须为 False