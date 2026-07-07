FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8020

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    -r requirements.txt

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY . /app

RUN mkdir -p /app/data /app/web/uploads /app/web/exports \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8020

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8020/healthz', timeout=3).read()"

CMD ["python", "server.py"]
