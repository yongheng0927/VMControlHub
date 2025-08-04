FROM python:3.10-slim

RUN rm -rf /etc/apt/sources.list.d/*.sources \
    && echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian bookworm main contrib non-free' > /etc/apt/sources.list \
    && echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian bookworm-updates main contrib non-free' >> /etc/apt/sources.list \
    && echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free' >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 2000 vmcontrolhub \
    && useradd -m -s /bin/bash -u 2000 -g 2000 vmcontrolhub \
    && mkdir -p /home/vmcontrolhub/.ssh \
    && chown -R vmcontrolhub:vmcontrolhub /home/vmcontrolhub \
    && chmod 700 /home/vmcontrolhub/.ssh

WORKDIR /home/vmcontrolhub

COPY --chown=vmcontrolhub:vmcontrolhub requirements.txt run.py .env ./
COPY --chown=vmcontrolhub:vmcontrolhub app/ ./app/
COPY --chown=vmcontrolhub:vmcontrolhub static/ ./static/

RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

USER vmcontrolhub

ENV PATH="/home/vmcontrolhub/.local/bin:${PATH}"

CMD ["python", "run.py"]