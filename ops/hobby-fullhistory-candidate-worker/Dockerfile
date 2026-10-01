FROM postgres:18-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates openssl \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages --no-cache-dir "psycopg[binary]>=3.2,<3.4"

WORKDIR /app
COPY run.py /app/run.py

CMD ["python3", "/app/run.py"]
