"""Django 설정.

비밀값·주소는 모두 환경변수(.env)에서 읽는다.
- Docker Compose: compose.yaml이 .env를 컨테이너 환경변수로 넣어 준다.
- 로컬 실행: 프로젝트 최상위의 .env를 python-dotenv로 읽는다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
# 이미 있는 환경변수는 덮어쓰지 않는다. ENV_FILE로 다른 파일을 지정할 수 있다(로컬 테스트용).
load_dotenv(os.getenv("ENV_FILE", BASE_DIR.parent / ".env"))


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY 환경변수가 없습니다. .env.example을 복사해 .env를 만드세요.")

DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 설치 패키지
    "rest_framework",
    # 직접 만든 앱 2개
    "accounts",
    "analyses",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL (POSTGRES_DB가 없으면 로컬 연습용 SQLite)
if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# 업로드 영상·수집 영상·결과 미리보기 (Django와 Celery가 같은 폴더를 공유)
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 로그인
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "analyses:index"
LOGOUT_REDIRECT_URL = "login"

# DRF: 로그인한 사용자만 API 사용 (브라우저 세션 + curl 테스트용 Basic 인증)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Celery (Redis = 메시지 브로커). 결과는 Celery 결과 저장소가 아니라 Django ORM으로 DB에 저장한다.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
if CELERY_BROKER_URL.startswith("filesystem://"):
    # Redis가 없는 로컬 연습용 브로커 (Docker에서는 Redis 사용)
    _broker_dir = BASE_DIR.parent / ".celery_broker"
    _broker_dir.mkdir(exist_ok=True)
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "data_folder_in": str(_broker_dir),
        "data_folder_out": str(_broker_dir),
    }

# FastAPI AI 서버 (Compose에서는 서비스 이름 fastapi 사용)
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8001").rstrip("/")
FASTAPI_TIMEOUT_SECONDS = int(os.getenv("FASTAPI_TIMEOUT_SECONDS", "300"))

# IP Webcam: 허용된 카메라만 사용 (형식: key|표시이름|URL, 여러 개는 쉼표)
# 사용자는 key만 고르고, 실제 URL은 서버(.env)에만 있다.
IP_WEBCAM_CAMERAS = {}
for _item in env_list("IP_WEBCAM_CAMERAS"):
    _parts = [part.strip() for part in _item.split("|")]
    if len(_parts) == 3 and _parts[0] and _parts[2]:
        IP_WEBCAM_CAMERAS[_parts[0]] = {"name": _parts[1] or _parts[0], "url": _parts[2]}
IP_WEBCAM_CAPTURE_SECONDS = float(os.getenv("IP_WEBCAM_CAPTURE_SECONDS", "8"))
IP_WEBCAM_CONNECT_TIMEOUT = float(os.getenv("IP_WEBCAM_CONNECT_TIMEOUT", "10"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"analyses": {"handlers": ["console"], "level": "INFO"}},
}
