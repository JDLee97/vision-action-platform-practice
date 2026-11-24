"""사람(Track ID)별 Feature 목록 → 30-Step Sequence(1,140) → Random Forest 예측."""

from __future__ import annotations

import time

import numpy as np

from src.sequence_utils import flatten_sequence, resample_sequence
from services.pose_pipeline import extract_tracks, render_preview


def predict_track(bundle, features, frame_ids) -> dict:
    """한 사람의 전체 Frame Feature를 학습 때와 같은 30 Step으로 맞춘 뒤 예측한다."""
    sequence = resample_sequence(
        np.stack(features),
        np.asarray(frame_ids),
        target_steps=bundle.sequence_steps,
    )
    row = flatten_sequence(sequence).reshape(1, -1)
    if row.shape[1] != bundle.feature_count:
        raise RuntimeError(f"Feature 수 불일치: {row.shape[1]} != {bundle.feature_count}")

    probabilities = bundle.classifier.predict_proba(row)[0]
    best = int(np.argmax(probabilities))
    confidence = float(probabilities[best])
    return {
        "action_label": str(bundle.classifier.classes_[best]),
        "confidence": round(confidence, 4),
        "uncertain": confidence < bundle.confidence_threshold,
        "probabilities": {
            str(name): round(float(p), 4)
            for name, p in zip(bundle.classifier.classes_, probabilities)
        },
    }


def analyze_video(video_path: str, bundle) -> dict:
    """영상 한 건을 처리해 API 응답용 dict를 만든다. 영상 자체를 못 읽으면 VideoReadError."""
    started = time.perf_counter()
    extraction = extract_tracks(video_path, bundle)

    predictions = []
    skipped = []
    for track_id, track in sorted(extraction.tracks.items()):
        valid = len(track.features)
        if valid < bundle.min_valid_frames:
            skipped.append({"track_id": track_id, "valid_frames": valid})
            continue
        result = predict_track(bundle, track.features, track.frame_ids)
        predictions.append(
            {
                "track_id": track_id,
                "valid_frames": valid,
                "seen_frames": track.seen_frames,
                **result,
            }
        )

    if predictions:
        status = "ok"
        message = f"{len(predictions)}명의 동작을 예측했습니다."
    elif extraction.person_frames == 0:
        status = "no_person"
        message = "영상에서 사람을 찾지 못했습니다."
    else:
        status = "too_short"
        message = (
            f"사람은 보였지만 유효한 Pose Frame이 {bundle.min_valid_frames}개 미만이라 "
            "동작을 판단할 수 없습니다. 몸 전체가 보이도록 더 길게 촬영하세요."
        )

    labels = {
        p["track_id"]: f"ID {p['track_id']} {p['action_label']} {p['confidence']:.0%}"
        for p in predictions
    }
    preview = render_preview(extraction, labels)

    return {
        "status": status,
        "message": message,
        "processing_ms": int((time.perf_counter() - started) * 1000),
        "video": {
            "frames": extraction.frame_count,
            "fps": round(extraction.fps, 2),
            "duration_sec": round(extraction.frame_count / extraction.fps, 2),
            "width": extraction.width,
            "height": extraction.height,
            "person_frames": extraction.person_frames,
        },
        "model": {
            "sequence_steps": bundle.sequence_steps,
            "feature_count": bundle.feature_count,
            "confidence_threshold": bundle.confidence_threshold,
        },
        "predictions": predictions,
        "skipped_tracks": skipped,
        "preview_jpeg": preview,
    }
