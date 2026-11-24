"""영상 → YOLO Pose + ByteTrack → 사람(Track ID)별 38-D Frame Feature 목록.

학습(5~6일차)과 같은 방식으로 Feature를 만든다.
- Keypoint: YOLO Pose의 픽셀 좌표 xy (COCO 17)
- Frame Feature: src.multi_person_utils.feature_from_keypoints (골반 중심·어깨 폭 정규화 34 + 관절각도 4)
- Sequence 변환은 action_inference.py에서 resample_sequence(30) → flatten_sequence(1,140)
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field

import cv2
import numpy as np

from src.multi_person_utils import feature_from_keypoints
from src.pose_utils import COCO_SKELETON

MAX_FRAMES = int(os.getenv("MAX_FRAMES", "900"))  # 30fps 기준 약 30초

# YOLO 추적기는 모델 객체 안에 상태를 저장하므로 한 번에 한 영상만 처리한다.
_track_lock = threading.Lock()


class VideoReadError(Exception):
    """영상 파일을 열 수 없거나 Frame이 없을 때."""


@dataclass
class TrackSequence:
    track_id: int
    features: list = field(default_factory=list)
    frame_ids: list = field(default_factory=list)
    seen_frames: int = 0
    best_box_conf: float = 0.0


@dataclass
class PoseExtraction:
    frame_count: int
    fps: float
    width: int
    height: int
    person_frames: int
    tracks: dict
    preview: tuple | None  # (대표 Frame, [(keypoints, keypoint_conf, track_id)])


def _draw_skeleton(frame, keypoints, kp_conf, color, label):
    for start, end in COCO_SKELETON:
        if kp_conf[start] < 0.3 or kp_conf[end] < 0.3:
            continue
        p1 = tuple(int(v) for v in keypoints[start])
        p2 = tuple(int(v) for v in keypoints[end])
        cv2.line(frame, p1, p2, color, 3, cv2.LINE_AA)
    for (x, y), conf in zip(keypoints, kp_conf):
        if conf >= 0.3:
            cv2.circle(frame, (int(x), int(y)), 4, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, (int(x), int(y)), 4, color, 1, cv2.LINE_AA)
    visible = keypoints[kp_conf >= 0.3]
    if len(visible):
        x, y = visible.min(axis=0)
        cv2.putText(frame, label, (int(x), max(20, int(y) - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)


TRACK_COLORS = [(222, 196, 46), (70, 70, 230), (60, 180, 75), (0, 140, 255), (200, 80, 200)]


def extract_tracks(video_path: str, bundle) -> PoseExtraction:
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise VideoReadError("영상 파일을 열 수 없습니다. MP4 등 지원 형식인지 확인하세요.")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    cfg = bundle.pose_config
    tracker = bundle.tracking_config.get("tracker", "bytetrack.yaml")

    tracks: dict[int, TrackSequence] = {}
    frame_id = 0
    person_frames = 0
    preview = None  # (사람 수, frame, [(kp, conf, tid)])

    with _track_lock:
        while frame_id < MAX_FRAMES:
            ok, frame = capture.read()
            if not ok or frame is None:
                break

            # 첫 Frame에서 추적기를 새로 만들고(persist=False), 이후에는 이어서 추적한다.
            result = bundle.pose_model.track(
                source=frame,
                persist=frame_id > 0,
                tracker=tracker,
                imgsz=cfg["image_size"],
                conf=cfg["person_confidence"],
                device=bundle.device,
                verbose=False,
            )[0]

            boxes = result.boxes
            kps = result.keypoints
            if boxes is not None and kps is not None and len(boxes) > 0 and kps.xy is not None:
                person_frames += 1
                xy_all = kps.xy.detach().cpu().numpy()
                conf_all = (
                    kps.conf.detach().cpu().numpy()
                    if kps.conf is not None
                    else np.ones(xy_all.shape[:2], dtype=np.float32)
                )
                ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
                box_conf = boxes.conf.detach().cpu().numpy()

                drawn = []
                for index, track_id in enumerate(ids):
                    if track_id is None or index >= len(xy_all):
                        continue
                    state = tracks.setdefault(int(track_id), TrackSequence(int(track_id)))
                    state.seen_frames += 1
                    state.best_box_conf = max(state.best_box_conf, float(box_conf[index]))
                    feature = feature_from_keypoints(xy_all[index])
                    if feature is not None:
                        state.features.append(feature)
                        state.frame_ids.append(frame_id)
                    drawn.append((xy_all[index], conf_all[index], int(track_id)))

                # 결과 미리보기: 가장 많은 사람이 보인 Frame(동률이면 영상 중간에 가까운 Frame)
                if drawn and (preview is None or len(drawn) > preview[0]):
                    preview = (len(drawn), frame.copy(), drawn)

            frame_id += 1

    capture.release()

    if frame_id == 0:
        raise VideoReadError("영상에서 Frame을 읽지 못했습니다. 파일이 손상되었을 수 있습니다.")

    return PoseExtraction(
        frame_count=frame_id,
        fps=fps,
        width=width,
        height=height,
        person_frames=person_frames,
        tracks=tracks,
        preview=None if preview is None else (preview[1], preview[2]),
    )


def render_preview(extraction: PoseExtraction, labels: dict[int, str]) -> bytes | None:
    """대표 Frame에 사람별 Skeleton과 'ID n 동작' 라벨을 그려 JPEG bytes로 반환한다."""
    if extraction.preview is None:
        return None
    image, drawn = extraction.preview
    image = image.copy()
    for kp, conf, tid in drawn:
        color = TRACK_COLORS[tid % len(TRACK_COLORS)]
        _draw_skeleton(image, kp, conf, color, labels.get(tid, f"ID {tid}"))
    scale = 720 / max(image.shape[:2])
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale)
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buffer.tobytes() if ok else None
