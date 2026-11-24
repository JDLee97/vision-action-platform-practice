# FastAPI AI 추론 서버 이미지 (CPU)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YOLO_CONFIG_DIR=/tmp/Ultralytics \
    YOLO_OFFLINE=1

# OpenCV 실행에 필요한 시스템 라이브러리
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# GPU 없는 환경에서도 실행되도록 CPU 전용 torch를 먼저 설치 (이미지 크기 절약)
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY requirements.txt .
RUN pip install -r requirements.txt

# 코드와 설정 복사 (모델 파일은 compose.yaml에서 ./ai_service/models 폴더를 마운트)
COPY . .

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
