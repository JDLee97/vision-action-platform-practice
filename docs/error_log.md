# 오류 기록 (발표 6번: 증상 → 확인한 곳 → 바꾼 것 → 검증)

## E01. OpenCV 버전이 학습 환경과 달라짐

- **증상:** `ai_service` 가상환경에서 `requirements.txt`에 `opencv-python-headless==5.0.0.93`을 적었는데 `cv2.__version__`이 `5.1.0`으로 나왔다.
- **확인한 곳:** `uv pip list`로 설치 목록을 보니 `opencv-python 5.1.x`(ultralytics가 의존성으로 설치)와 `opencv-python-headless 5.0.0.93`이 **둘 다** 설치되어 있었다. 두 패키지는 같은 `cv2` 모듈 이름을 쓰므로 나중에 설치된 쪽이 덮어쓴다.
- **바꾼 것:** headless를 빼고, 학습 환경(subject10_pose_action)과 같은 `opencv-python==5.0.0.93`만 고정. 두 패키지를 지우고 다시 설치.
- **검증:** `python -c "import cv2; print(cv2.__version__)"` → `5.0.0`. 같은 영상으로 다시 추론해 결과가 같은지 확인.

## E02. `.env`를 bash로 `source`하면 문법 오류

- **증상:** 로컬 테스트용 환경변수 파일을 `set -a; . .env.local-test`로 읽자 `syntax error near unexpected token '('`.
- **확인한 곳:** 오류 줄 번호(5번째 줄) = `IP_WEBCAM_CAMERAS=demo|테스트 스트림(가짜 카메라)|...`. bash는 `|`, `(`, 공백을 명령어 문법으로 해석한다.
- **바꾼 것:** 셸에서 읽지 않고 Django가 `python-dotenv`로 직접 읽게 했다. `settings.py`에 `ENV_FILE` 환경변수로 읽을 파일을 바꿀 수 있게 추가.
- **검증:** `ENV_FILE=.env.local-test python manage.py check` → 오류 없음, 카메라 목록이 화면에 표시됨.

## E04. 새 분석을 시작했는데 이전 작업의 결과·Skeleton 이미지가 그대로 보임

- **증상:** 두 사람 영상 분석이 끝난 뒤 손상된 파일로 새 분석을 시작하자, 상태 카드는 `작업 #4 실패`인데 미리보기에는 이전 작업 #3의 Skeleton 이미지가 남아 있었다. 자동 캡처 스크립트도 이전 작업의 `완료` 표시를 보고 바로 다음 단계로 넘어갔다.
- **확인한 곳:** `static/js/analyses.js`의 시작 버튼 처리. 새 작업을 등록하기 전에 단계 표시·결과 표·미리보기를 초기화하는 코드가 없었다. 실패한 작업은 `result_image`가 없어서 이전 이미지가 교체되지 않았다.
- **바꾼 것:** 시작 버튼을 누르면 `render({status: "PENDING", stage: "queued"})`로 화면을 초기화하고, 업로드 모드에서는 선택한 영상을 다시 표시. 캡처 스크립트는 새 작업 번호가 표시될 때까지 기다린 뒤 완료를 확인하도록 수정.
- **검증:** 정상 → 실패 순서로 연속 분석 → 실패 작업에서 이전 이미지가 보이지 않음 (`docs/evidence/T09_broken_file.png`).

## E05. 다른 회원 권한 테스트에서 404가 아니라 403이 나옴

- **증상:** 브라우저 자동화에서 HTTP Basic 계정(student02)으로 `/api/v1/analyses/1/`을 열자 `403 자격 인증 데이터가 제공되지 않았습니다`가 나왔다. 기대한 결과는 `404`(남의 작업은 존재 자체가 보이지 않음).
- **확인한 곳:** DRF 인증 순서. `DEFAULT_AUTHENTICATION_CLASSES`의 첫 번째가 `SessionAuthentication`이라 인증 실패 시 `WWW-Authenticate` 헤더 없이 403을 돌려준다. 브라우저는 헤더가 없으면 Basic 계정 정보를 보내지 않으므로 **로그인 자체가 안 된 상태**였다(권한 문제가 아님).
- **바꾼 것:** 캡처는 student02로 로그인 화면을 통해 세션 로그인한 뒤 접근하도록 변경. curl은 `-u`로 처음부터 Basic 헤더를 보내 검사.
- **검증:** `docs/evidence/T07_permission.txt` — GET·PATCH·DELETE 모두 404, student02 목록 count=0, 본인(student01)은 200, 비로그인은 403.

## E06. 같은 영상인데 로컬(GPU)과 Docker(CPU)의 신뢰도가 조금 다름 (관찰)

- **증상:** `S01_wave_train.mp4`가 로컬 GPU에서는 wave 0.6367, Docker CPU에서는 wave 0.6267.
- **확인한 곳:** 예측 Label은 같고 확률만 0.01 차이. YOLO Pose를 GPU/CPU에서 실행하면 Keypoint 좌표가 소수점 단위로 달라지고, 그 차이가 1,140 Feature를 거쳐 Random Forest 투표에 조금 반영된다.
- **바꾼 것:** 없음. README에 Docker 이미지는 CPU torch를 사용한다고 기록.
- **검증:** 6개 학습 영상 모두 Label은 동일.

## E03. 한 사람 영상에서 Track ID가 2개 생김 (관찰)

- **증상:** 학습 영상 `S01_A002_T01.mp4`(다리 들기, 1명)를 분석하자 `ID 1`, `ID 3` 두 개의 결과가 나왔다.
- **확인한 곳:** FastAPI 응답의 `valid_frames`가 두 Track 모두 64로 같았다 → 같은 사람이 같은 Frame에서 두 번 검출된(중복 Box) 경우로 판단.
- **바꾼 것:** (현재) 유효 Frame이 `min_valid_frames`(10) 미만인 짧은 Track만 제외. 중복 Box는 추가 개선 과제로 남김(겹침 IoU가 큰 Track 병합 등).
- **검증:** 응답의 `skipped_tracks`에 짧은 Track이 따로 표시되는지 확인. 2인 영상(SBU)은 ID별로 분리됨.
