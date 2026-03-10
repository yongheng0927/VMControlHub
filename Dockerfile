FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 2000 vmcontrolhub \
    && useradd -m -s /bin/bash -u 2000 -g 2000 vmcontrolhub \
    && mkdir -p /home/vmcontrolhub/.ssh \
    && chown -R vmcontrolhub:vmcontrolhub /home/vmcontrolhub \
    && chmod 700 /home/vmcontrolhub/.ssh

WORKDIR /home/vmcontrolhub

COPY --chown=vmcontrolhub:vmcontrolhub requirements.txt run.py .env gunicorn_config.py ./
COPY --chown=vmcontrolhub:vmcontrolhub app/ ./app/
COPY --chown=vmcontrolhub:vmcontrolhub static/ ./static/
COPY --chown=vmcontrolhub:vmcontrolhub entrypoint.sh /usr/local/bin/entrypoint.sh

RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

RUN pip install --no-cache-dir -r requirements.txt

USER vmcontrolhub

ENV PATH="/home/vmcontrolhub/.local/bin:${PATH}"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["gunicorn", "-c", "gunicorn_config.py", "run:app"]