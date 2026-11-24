#!/usr/bin/env bash
# 사용: submit_and_wait.sh <영상 파일> <제목> [대기초]
cd ~/ai_vision/vision-action-platform-practice
PW='VisionAi!2026'
ID=$(curl -s -u "student01:$PW" -F input_type=upload -F "title=$2" -F "video=@$1" localhost:8000/api/v1/analyses/ \
     | python3 -c 'import sys,json;j=json.load(sys.stdin);print(j["id"])')
echo "요청: POST /api/v1/analyses/ ($1) → 작업 id=$ID PENDING"
for i in $(seq 1 ${3:-40}); do
  S=$(curl -s -u "student01:$PW" localhost:8000/api/v1/analyses/$ID/status/)
  if echo "$S" | grep -qE '"status":"(SUCCESS|FAILURE)"'; then break; fi
  sleep 1
done
echo "$S" | python3 -c 'import sys,json;j=json.load(sys.stdin);print("결과: id=",j["id"],"status=",j["status"],"| error_message=",j["error_message"] or "-","| predictions=",[(p["track_id"],p["action_label"],p["confidence"]) for p in j["predictions"]])'
