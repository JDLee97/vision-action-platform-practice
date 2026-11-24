"""6일차 학습 산출물(Joblib·JSON)과 YOLO Pose 가중치를 읽고 규격을 검사한다.

서버가 시작될 때 한 번만 호출하고, 요청마다 같은 객체를 재사용한다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import joblib

from src.common import resolve_device
from src.sequence_utils import FRAME_FEATURE_NAMES, sequence_feature_names

AI_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(os.getenv("MODEL_DIR", AI_ROOT / "models"))

# 수업에서 다룬 6개 Action (ID 순서). 모델 classes_와 집합이 일치해야 한다.
ACTIONS = {
    "A001": "bend_return",
    "A002": "leg_raise_lower",
    "A003": "walk_turn_walk",
    "A004": "drink_return",
    "A005": "sit_stand",
    "A006": "wave",
}


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@dataclass
class ModelBundle:
    """추론에 필요한 모든 객체를 한곳에 묶어 둔다."""

    classifier: object
    feature_columns: list[str]
    training_info: dict
    pose_model: object
    pose_config: dict
    realtime_config: dict
    tracking_config: dict
    device: object
    sequence_steps: int
    min_valid_frames: int
    confidence_threshold: float
    classes: list[str] = field(default_factory=list)

    @property
    def feature_count(self) -> int:
        return len(self.feature_columns)


def load_bundle() -> ModelBundle:
    """모델·Feature 순서·학습 정보·Pose 가중치를 읽고, 서로 맞는지 검사한다."""

    model_path = MODEL_DIR / "rf_action_baseline.joblib"
    columns_path = MODEL_DIR / "rf_feature_columns.json"
    info_path = MODEL_DIR / "rf_training_info.json"

    for path in (model_path, columns_path, info_path):
        if not path.exists():
            raise FileNotFoundError(f"모델 산출물이 없습니다: {path}")

    pose_config = _read_json(AI_ROOT / "project.json")
    realtime_config = _read_json(AI_ROOT / "day07_realtime.json")
    tracking_config = _read_json(AI_ROOT / "day08_multi_person.json")

    pose_path = MODEL_DIR / pose_config["pose_model"]
    if not pose_path.exists():
        raise FileNotFoundError(f"YOLO Pose 가중치가 없습니다: {pose_path}")

    # joblib.load()는 직접 학습한 신뢰 가능한 파일에만 사용한다.
    classifier = joblib.load(model_path)
    feature_columns = _read_json(columns_path)
    training_info = _read_json(info_path)

    steps = int(training_info["sequence_steps"])
    expected_columns = sequence_feature_names(steps)

    # ① Feature 수: 30 Step × 38 = 1,140
    if len(FRAME_FEATURE_NAMES) * steps != len(feature_columns):
        raise RuntimeError(
            f"Feature 수 불일치: {len(FRAME_FEATURE_NAMES)}×{steps} != {len(feature_columns)}"
        )
    if int(training_info["feature_count"]) != len(feature_columns):
        raise RuntimeError("rf_training_info.json의 feature_count가 JSON 컬럼 수와 다릅니다.")
    if int(getattr(classifier, "n_features_in_", len(feature_columns))) != len(feature_columns):
        raise RuntimeError("Joblib 모델의 n_features_in_이 Feature 컬럼 수와 다릅니다.")

    # ② Feature 순서: 학습 때 만든 이름 순서와 지금 코드가 만드는 순서가 같아야 한다.
    if list(feature_columns) != expected_columns:
        raise RuntimeError("rf_feature_columns.json 순서가 현재 Feature 생성 코드와 다릅니다.")

    # ③ Class: 모델 classes_ = 학습 정보 = 수업 6개 Action
    classes = [str(name) for name in classifier.classes_]
    if sorted(classes) != sorted(training_info["classes"]):
        raise RuntimeError("model.classes_와 rf_training_info.json의 classes가 다릅니다.")
    if sorted(classes) != sorted(ACTIONS.values()):
        raise RuntimeError(f"6개 Action과 모델 Class가 다릅니다: {classes}")

    # YOLO Pose는 무거운 import이므로 검사가 끝난 뒤에 불러온다.
    from ultralytics import YOLO

    device = resolve_device(os.getenv("POSE_DEVICE", pose_config.get("device", "auto")))
    pose_model = YOLO(str(pose_path))

    return ModelBundle(
        classifier=classifier,
        feature_columns=list(feature_columns),
        training_info=training_info,
        pose_model=pose_model,
        pose_config=pose_config,
        realtime_config=realtime_config,
        tracking_config=tracking_config,
        device=device,
        sequence_steps=steps,
        min_valid_frames=int(training_info.get("min_valid_frames", 10)),
        confidence_threshold=float(realtime_config.get("confidence_threshold", 0.55)),
        classes=classes,
    )
