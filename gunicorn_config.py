# ==========================================
# VMControlHub Gunicorn 动态优化配置文件
# ==========================================

import multiprocessing
import os

# 内存池限制 (减少内存碎片，针对 Python 多进程场景优化)
os.environ["MALLOC_ARENA_MAX"] = "2"

# 1. 自动获取 CPU 核心数
cores = multiprocessing.cpu_count()

# 2. 网络绑定
# 容器内部监听 5000 端口
bind = "0.0.0.0:5000"

# 3. 动态工作进程设置 (关键优化)
# 逻辑：核心数越多，进程数越多，但上限设为 6 以节省内存
workers = max(2, min(cores, 6))

# 4. 线程设置
# 每个进程配合 8 个线程，总并发能力为 workers * threads (6 * 8 = 48)
# 注：sync 模式下使用多线程需配合 gthread，若保持 pure sync，threads 建议设为 1
# 若要启用多线程，需将 worker_class 改为 "gthread"
threads = 8
worker_class = "sync"  # 针对系统命令调用（qm/pvesh）保持 sync 模式最稳妥
preload_app = True  # 预加载应用代码，共享内存，节省资源并加快 worker 启动

# 5. 核心：真实 IP 处理
# 信任来自 Docker 网络或 Nginx 代理的请求
forwarded_allow_ips = '*'
proxy_allow_ips = "*"

# 6. 日志配置
# 输出到标准输出，方便通过 `docker logs -f` 查看
accesslog = "-"
errorlog = "-"
loglevel = "info"

# 针对 Nginx 代理优化的日志格式 (记录真实客户端 IP)
access_log_format = '%({X-Real-IP}i)s %({X-Forwarded-For}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# 7. 超时与性能 (针对虚拟机操作优化)
# 启动大内存 VM 可能耗时较长，设为 60 秒
timeout = 60
keepalive = 5
graceful_timeout = 30
worker_tmp_dir = "/dev/shm" # 使用内存文件系统，减少磁盘 IO
max_requests = 500  # 处理 500 个请求后 worker 自动重启 (防止内存泄漏)
max_requests_jitter = 100 # 随机抖动 0-100，避免所有 worker 同时重启

# 8. 进程管理
proc_name = "vmcontrolhub_app"
daemon = False  # Docker 模式必须为 False (由容器引擎管理生命周期)