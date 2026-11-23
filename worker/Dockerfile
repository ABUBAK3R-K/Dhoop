FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# System libs required by bpy wheel + ffmpeg + fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg libgl1 libegl1 libxi6 libxfixes3 libxrender1 libxxf86vm1 \
      libxkbcommon0 libsm6 libice6 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN useradd -m dhoop && mkdir -p /data && chown -R dhoop /data
USER dhoop
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
