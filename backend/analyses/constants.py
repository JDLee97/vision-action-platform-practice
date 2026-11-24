"""수업에서 다룬 6개 Action 정의. 모델 classes_와 같은 영문 Label을 사용한다."""

ACTIONS = [
    # (ID, 모델 Label, 화면 표시 이름)
    ("A001", "bend_return", "허리 굽혔다 펴기"),
    ("A002", "leg_raise_lower", "한쪽 다리 들었다 내리기"),
    ("A003", "walk_turn_walk", "걷다가 방향 바꾸기"),
    ("A004", "drink_return", "음료 마시기"),
    ("A005", "sit_stand", "앉았다 일어나기"),
    ("A006", "wave", "손 흔들기"),
]

ACTION_CHOICES = [(label, f"{action_id} {name}") for action_id, label, name in ACTIONS]
ACTION_DISPLAY = {label: name for _, label, name in ACTIONS}
ACTION_ID = {label: action_id for action_id, label, _ in ACTIONS}

# 이 값보다 신뢰도가 낮으면 "불확실"로 표시 (7일차 confidence_threshold)
UNCERTAIN_THRESHOLD = 0.55
