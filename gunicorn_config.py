# Gunicorn 配置文件

# 绑定地址和端口
bind = "0.0.0.0:5000"

# 工作进程数（建议 CPU 核心数 * 2 + 1）
workers = 4

# 工作模式（sync 或 gevent）
worker_class = "sync"

# 日志配置
accesslog = "-"
errorlog = "-"
loglevel = "info"

# 超时设置（秒）
timeout = 30

# 优雅重启
graceful_timeout = 30

# 保护模式
keepalive = 5

# 进程名
proc_name = "vmcontrolhub"