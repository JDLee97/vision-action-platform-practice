"""허용된 IP Webcam에서 정해진 시간(기본 8초)만 프레임을 읽어 MP4로 저장한다.

카메라 URL은 .env의 IP_WEBCAM_CAMERAS에만 있고, 사용자는 키만 고른다.
(휴대폰 IP Webcam 앱: http://<휴대폰IP>:8080/video)
"""

import os
import threading
import time

import cv2
from django.conf import settings


class CameraError(Exception):
    pass


def camera_url(camera_key: str) -> str:
    camera = settings.IP_WEBCAM_CAMERAS.get(camera_key)
    if camera is None:
        raise CameraError("허용되지 않은 카메라입니다.")
    return camera["url"]


def _open(url: str, timeout: float):
    """VideoCapture 생성이 네트워크 문제로 멈추지 않도록 시간 제한을 둔다."""
    holder = {}

    def target():
        holder["capture"] = cv2.VideoCapture(url)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    capture = holder.get("capture")
    if thread.is_alive() or capture is None or not capture.isOpened():
        raise CameraError(f"카메라에 {int(timeout)}초 안에 연결하지 못했습니다. 같은 네트워크인지, 앱이 실행 중인지 확인하세요.")
    return capture


def capture_clip(camera_key: str, output_path: str, seconds: float | None = None) -> dict:
    seconds = float(seconds or settings.IP_WEBCAM_CAPTURE_SECONDS)
    capture = _open(camera_url(camera_key), settings.IP_WEBCAM_CONNECT_TIMEOUT)

    writer = None
    frames = 0
    started = time.monotonic()
    last_frame_time = started
    try:
        while time.monotonic() - started < seconds:
            ok, frame = capture.read()
            now = time.monotonic()
            if not ok or frame is None:
                # 잠깐의 끊김은 기다리고, 3초 이상 프레임이 없으면 실패로 처리
                if now - last_frame_time > 3:
                    raise CameraError(f"카메라 연결이 끊겼습니다. ({frames}프레임 수집 후 중단)")
                time.sleep(0.05)
                continue
            last_frame_time = now
            if writer is None:
                height, width = frame.shape[:2]
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (width, height))
            writer.write(frame)
            frames += 1
    finally:
        capture.release()
        if writer is not None:
            writer.release()

    elapsed = time.monotonic() - started
    if frames == 0:
        raise CameraError("카메라에서 프레임을 받지 못했습니다.")

    # 실제 수집 FPS로 다시 기록해야 영상 길이가 맞다 → FastAPI는 frame 순서만 쓰므로 그대로 사용
    return {"frames": frames, "seconds": round(elapsed, 2), "fps": round(frames / elapsed, 2)}


def grab_snapshot_jpeg(camera_key: str) -> bytes:
    """미리보기용 한 장. 브라우저에 카메라 주소를 노출하지 않기 위해 서버가 대신 가져온다."""
    capture = _open(camera_url(camera_key), 5)
    try:
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok or frame is None:
        raise CameraError("카메라에서 이미지를 받지 못했습니다.")
    scale = 640 / max(frame.shape[:2])
    if scale < 1:
        frame = cv2.resize(frame, None, fx=scale, fy=scale)
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buffer.tobytes()
