"""시연·테스트용 계정 생성: 관리자 teacher, 일반 회원 student01·student02.

python manage.py create_demo_users
비밀번호는 DEMO_USER_PASSWORD 환경변수(없으면 VisionAi!2026). 실제 서비스에서는 사용하지 마세요.
"""

import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "시연용 관리자·일반 회원 계정을 만든다."

    def handle(self, *args, **options):
        password = os.getenv("DEMO_USER_PASSWORD", "VisionAi!2026")
        for username, is_staff in [("teacher", True), ("student01", False), ("student02", False)]:
            user, created = User.objects.get_or_create(username=username)
            user.is_staff = is_staff
            user.is_superuser = is_staff
            user.set_password(password)
            user.save()
            self.stdout.write(f"{'생성' if created else '갱신'}: {username} ({'관리자' if is_staff else '일반 회원'})")
