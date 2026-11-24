"""FastAPI AI 서버에 영상을 HTTP로 보내고 응답·타임아웃·오류를 정리한다."""

from pathlib import Path

import requests
from django.conf import settings


class AIServiceError(Exception):
    """AI 서버 호출 실패. 메시지는 그대로 사용자에게 보여 줄 수 있게 작성한다."""


def request_prediction(video_path: str) -> dict:
    url = f"{settings.FASTAPI_URL}/api/v1/predict/"
    try:
        with open(video_path, "rb") as file:
            response = requests.post(
                url,
                files={"file": (Path(video_path).name, file, "video/mp4")},
                timeout=(5, settings.FASTAPI_TIMEOUT_SECONDS),  # (연결, 응답 대기)
            )
    except FileNotFoundError as error:
        raise AIServiceError("분석할 영상 파일을 찾을 수 없습니다.") from error
    except requests.ConnectionError as error:
        raise AIServiceError("AI 서버(FastAPI)에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.") from error
    except requests.Timeout as error:
        raise AIServiceError(f"AI 서버 응답이 {settings.FASTAPI_TIMEOUT_SECONDS}초 안에 오지 않았습니다.") from error

    if response.status_code != 200:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise AIServiceError(f"AI 서버 오류({response.status_code}): {detail}")

    return response.json()
