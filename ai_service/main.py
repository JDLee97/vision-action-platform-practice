"""FastAPI AI 추론 서버.

실행: (ai_service 폴더에서) uvicorn main:app --host 0.0.0.0 --port 8001
문서: http://localhost:8001/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from routers import predictions
from services.model_loader import ACTIONS, load_bundle

logger = logging.getLogger("ai_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 한 번만 모델을 읽어 요청마다 재사용한다.
    app.state.bundle = None
    app.state.load_error = None
    try:
        app.state.bundle = load_bundle()
        logger.warning(
            "모델 로드 완료: classes=%s features=%d device=%s",
            app.state.bundle.classes,
            app.state.bundle.feature_count,
            app.state.bundle.device,
        )
    except Exception as error:  # 모델 파일이 없을 때도 /health로 이유를 볼 수 있게 한다.
        app.state.load_error = str(error)
        logger.exception("모델 로드 실패")
    yield


app = FastAPI(title="Vision AI 동작 추론 서버", version="1.0.0", lifespan=lifespan)
app.include_router(predictions.router)


@app.get("/health", summary="모델 로드 상태")
def health(request: Request):
    bundle = request.app.state.bundle
    if bundle is None:
        return {"status": "error", "model_loaded": False, "error": request.app.state.load_error}
    return {
        "status": "ok",
        "model_loaded": True,
        "classes": bundle.classes,
        "actions": ACTIONS,
        "feature_count": bundle.feature_count,
        "sequence_steps": bundle.sequence_steps,
        "min_valid_frames": bundle.min_valid_frames,
        "confidence_threshold": bundle.confidence_threshold,
        "device": str(bundle.device),
        "training_subjects": bundle.training_info.get("subjects"),
    }
