FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 2000 vmcontrolhub \
    && useradd -m -s /bin/bash -u 2000 -g 2000 vmcontrolhub \
    && mkdir -p /home/vmcontrolhub/.ssh \
    && chown -R vmcontrolhub:vmcontrolhub /home/vmcontrolhub \
    && chmod 700 /home/vmcontrolhub/.ssh

WORKDIR /home/vmcontrolhub

USER vmcontrolhub

VOLUME ["/home/vmcontrolhub/.ssh"]

COPY --chown=vmcontrolhub:vmcontrolhub  requirements.txt docker-entrypoint.sh .env gunicorn_config.py run.py ./

RUN pip install -r requirements.txt

COPY --chown=vmcontrolhub:vmcontrolhub static ./static/

COPY --chown=vmcontrolhub:vmcontrolhub app ./app/

ENV PATH="/home/vmcontrolhub/.local/bin:${PATH}"

ENTRYPOINT ["/home/vmcontrolhub/docker-entrypoint.sh"]