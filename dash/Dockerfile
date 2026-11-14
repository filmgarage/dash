ARG BUILD_FROM
FROM $BUILD_FROM
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
COPY app /app
ENV PATH="/opt/venv/bin:$PATH"
CMD ["python3", "/app/main.py"]
