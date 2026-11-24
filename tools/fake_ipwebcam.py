"""휴대폰이 없을 때 쓰는 가짜 IP Webcam.

MP4 파일을 반복 재생하면서 IP Webcam 앱과 같은 MJPEG 주소(/video)와 한 장 주소(/shot.jpg)를 제공한다.
Celery Worker는 실제 휴대폰과 똑같이 cv2.VideoCapture("http://.../video")로 읽는다.

실행 예 (backend 가상환경 또는 opencv가 있는 Python):
    python tools/fake_ipwebcam.py samples/wave.mp4 --port 8090
.env 허용 목록 예:
    로컬 실행:  IP_WEBCAM_CAMERAS=demo|테스트 스트림|http://localhost:8090/video
    Docker:    IP_WEBCAM_CAMERAS=demo|테스트 스트림|http://host.docker.internal:8090/video
"""

import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


class FrameSource:
    def __init__(self, path: str):
        self.path = path
        self.capture = cv2.VideoCapture(path)
        if not self.capture.isOpened():
            raise SystemExit(f"영상을 열 수 없습니다: {path}")
        self.fps = self.capture.get(cv2.CAP_PROP_FPS) or 30
        self.lock = threading.Lock()
        self.jpeg = None
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        delay = 1.0 / self.fps
        while True:
            ok, frame = self.capture.read()
            if not ok:  # 끝나면 처음부터 반복
                self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                with self.lock:
                    self.jpeg = buffer.tobytes()
            time.sleep(delay)

    def latest(self):
        with self.lock:
            return self.jpeg


def make_handler(source: FrameSource):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path.startswith("/shot.jpg"):
                data = source.latest()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if self.path.startswith("/video"):
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                try:
                    while True:
                        data = source.latest()
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(data)}\r\n\r\n".encode())
                        self.wfile.write(data + b"\r\n")
                        time.sleep(1.0 / source.fps)
                except (BrokenPipeError, ConnectionResetError):
                    return
            self.send_error(404)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    source = FrameSource(args.video)
    while source.latest() is None:
        time.sleep(0.05)
    print(f"가짜 IP Webcam 실행: http://localhost:{args.port}/video  (Ctrl+C로 종료)")
    ThreadingHTTPServer((args.host, args.port), make_handler(source)).serve_forever()


if __name__ == "__main__":
    main()
