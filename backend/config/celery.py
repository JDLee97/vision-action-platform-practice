"""Celery 앱 생성.

실행: (backend 폴더에서) celery -A config worker -l info
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
# settings.py의 CELERY_로 시작하는 설정을 읽는다.
app.config_from_object("django.conf:settings", namespace="CELERY")
# 설치된 앱의 tasks.py(analyses/tasks.py)를 자동으로 찾는다.
app.autodiscover_tasks()
