"""Celery Worker가 보낸 영상 한 건을 받아 사람별 예측 JSON을 돌려준다. (DB 접근 없음)"""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from services.action_inference import analyze_video
from services.pose_pipeline import VideoReadError

router = APIRouter(tags=["predictions"])

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))


def _run(request: Request, file: UploadFile) -> dict:
    bundle = getattr(request.app.state, "bundle", None)
    if bundle is None:
        raise HTTPException(status_code=503, detail="모델이 아직 로드되지 않았습니다.")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다({suffix or '확장자 없음'}). MP4 영상을 보내세요.",
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        shutil.copyfileobj(file.file, temp)
        temp_path = temp.name

    try:
        size_mb = os.path.getsize(temp_path) / 1024 / 1024
        if size_mb == 0:
            raise HTTPException(status_code=400, detail="빈 파일입니다.")
        if size_mb > MAX_UPLOAD_MB:
            raise HTTPException(status_code=413, detail=f"영상은 {MAX_UPLOAD_MB}MB 이하만 분석합니다.")
        try:
            result = analyze_video(temp_path, bundle)
        except VideoReadError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        os.unlink(temp_path)

    preview = result.pop("preview_jpeg")
    result["preview_jpeg_base64"] = base64.b64encode(preview).decode() if preview else None
    result["filename"] = file.filename
    return result


# 정의된 함수가 동기(def)이므로 FastAPI가 별도 스레드에서 실행한다 → 이벤트 루프를 막지 않음.
@router.post("/api/v1/predict/", summary="영상 한 건의 사람별 동작 예측")
def predict(request: Request, file: UploadFile = File(..., description="분석할 MP4 영상")):
    return _run(request, file)


@router.post("/predict/video", summary="(별칭) 과제 문서의 POST /predict/video", include_in_schema=True)
def predict_video(request: Request, file: UploadFile = File(...)):
    return _run(request, file)
