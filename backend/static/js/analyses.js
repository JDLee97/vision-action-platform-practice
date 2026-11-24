// 사용자 분석 화면
// 1) 분석 시작: POST /api/v1/analyses/ → 작업 ID를 바로 받음(202)
// 2) 상태 조회: GET /api/v1/analyses/{id}/status/ 를 1.5초마다 호출
// 3) 완료(SUCCESS/FAILURE)되면 사람별 결과·Skeleton 미리보기·최근 이력 갱신
(() => {
  const { apiBase, snapshotUrl, csrfToken } = window.APP;
  const captureSeconds = JSON.parse(document.getElementById("capture-seconds").textContent);
  const $ = (id) => document.getElementById(id);

  const STAGES = ["queued", "collecting", "analyzing", "done"];
  const POLL_MS = 1500;

  let mode = "upload";
  let selectedFile = null;
  let pollTimer = null;
  let snapshotTimer = null;
  let currentJobId = null;
  let localVideoUrl = null;

  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: { "X-CSRFToken": csrfToken, Accept: "application/json", ...(options.headers || {}) },
    });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = typeof data === "object"
        ? Object.entries(data).map(([k, v]) => (k === "detail" ? v : `${k}: ${[].concat(v).join(" ")}`)).join(" / ")
        : String(data);
      throw new Error(message || `요청 실패 (${response.status})`);
    }
    return data;
  }

  // ---------------- 미리보기 ----------------
  function showPlaceholder(text) {
    $("preview-video").hidden = true;
    $("preview-image").hidden = true;
    $("preview-badge").hidden = true;
    $("preview-placeholder").hidden = false;
    $("preview-placeholder").textContent = text;
  }
  function showVideo(url) {
    $("preview-placeholder").hidden = true;
    $("preview-image").hidden = true;
    $("preview-badge").hidden = true;
    const video = $("preview-video");
    video.src = url;
    video.hidden = false;
  }
  function showImage(url, badge) {
    $("preview-placeholder").hidden = true;
    $("preview-video").hidden = true;
    $("preview-video").pause();
    const image = $("preview-image");
    image.src = url;
    image.hidden = false;
    $("preview-badge").hidden = !badge;
    $("preview-badge").textContent = badge || "";
  }

  // ---------------- 탭 전환 ----------------
  function setMode(next) {
    mode = next;
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.mode === mode));
    $("upload-panel").hidden = mode !== "upload";
    $("ipwebcam-panel").hidden = mode !== "ipwebcam";
    $("input-title").textContent = mode === "upload" ? "영상 미리보기" : "IP Webcam 미리보기";
    stopSnapshot();
    if (mode === "upload") {
      $("action-meta").textContent = selectedFile ? selectedFile.name : "영상 업로드 분석";
      selectedFile ? showVideo(localVideoUrl) : showPlaceholder("분석할 MP4 영상을 선택하세요");
    } else {
      $("action-meta").innerHTML = `수집 시간 <b>${captureSeconds}초</b>`;
      startSnapshot();
    }
  }
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => setMode(tab.dataset.mode)));

  // ---------------- 파일 선택 ----------------
  function selectFile(file) {
    if (!file) return;
    selectedFile = file;
    if (localVideoUrl) URL.revokeObjectURL(localVideoUrl);
    localVideoUrl = URL.createObjectURL(file);
    $("file-name").textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(1)}MB)`;
    $("action-meta").textContent = file.name;
    showVideo(localVideoUrl);
  }
  $("video-file").addEventListener("change", (e) => selectFile(e.target.files[0]));
  const dropzone = $("dropzone");
  ["dragenter", "dragover"].forEach((type) => dropzone.addEventListener(type, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((type) => dropzone.addEventListener(type, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); }));
  dropzone.addEventListener("drop", (e) => selectFile(e.dataTransfer.files[0]));

  // ---------------- IP Webcam 미리보기 (서버가 대신 한 장씩 가져옴) ----------------
  function stopSnapshot() {
    clearTimeout(snapshotTimer);
    snapshotTimer = null;
  }
  function startSnapshot() {
    stopSnapshot();
    const key = $("camera-key").value;
    if (!key) { showPlaceholder("등록된 카메라가 없습니다. .env의 IP_WEBCAM_CAMERAS를 확인하세요."); return; }
    showPlaceholder("카메라에 연결하는 중…");
    const loop = async () => {
      if (mode !== "ipwebcam") return;
      try {
        const response = await fetch(snapshotUrl.replace("CAMERA_KEY", encodeURIComponent(key)) + `?t=${Date.now()}`, { credentials: "same-origin" });
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "카메라 연결 실패");
        const blob = await response.blob();
        const old = $("preview-image").dataset.objectUrl;
        const url = URL.createObjectURL(blob);
        showImage(url, "LIVE 미리보기");
        $("preview-image").dataset.objectUrl = url;
        if (old) URL.revokeObjectURL(old);
        snapshotTimer = setTimeout(loop, 1200);
      } catch (error) {
        showPlaceholder(`${error.message} — '미리보기 연결'을 눌러 다시 시도하세요.`);
      }
    };
    loop();
  }
  $("camera-refresh").addEventListener("click", startSnapshot);
  $("camera-key").addEventListener("change", startSnapshot);

  // ---------------- 상태·결과 표시 ----------------
  function renderStepper(job) {
    const index = STAGES.indexOf(job.stage);
    document.querySelectorAll(".step").forEach((step) => {
      const i = STAGES.indexOf(step.dataset.stage);
      step.className = "step";
      if (job.status === "SUCCESS") step.classList.add(i === 3 ? "success" : "done");
      else if (job.status === "FAILURE") step.classList.add(i === 3 ? "failure" : "done");
      else if (i < index) step.classList.add("done");
      else if (i === index) step.classList.add("current");
      step.querySelector(".dot").textContent = job.status === "FAILURE" && i === 3 ? "!" : "✓";
    });
    $("done-label").textContent = job.status === "FAILURE" ? "실패" : "완료";
    $("job-label").textContent = `작업 #${job.id} · ${job.status_display}`;

    const text = $("status-text");
    text.classList.toggle("error", job.status === "FAILURE");
    if (job.status === "FAILURE") text.textContent = `실패 사유: ${job.error_message || "알 수 없는 오류"}`;
    else if (job.status === "SUCCESS") text.textContent = job.result_message || "분석이 완료되었습니다.";
    else if (job.stage === "collecting") text.textContent = job.input_type === "ipwebcam" || mode === "ipwebcam"
      ? `카메라 앞에서 동작을 수행하세요. ${captureSeconds}초 동안 영상을 수집합니다…` : "영상을 준비하는 중…";
    else if (job.stage === "analyzing") text.textContent = "YOLO Pose → 30-Step Sequence → Random Forest로 분석 중…";
    else text.textContent = "작업이 대기열(Redis)에 등록되었습니다. Worker가 가져가기를 기다리는 중…";
  }

  function renderResults(job) {
    const rows = job.predictions || [];
    $("result-body").innerHTML = rows.map((p) => `
      <tr>
        <td>${p.track_id}</td>
        <td class="action">${escapeHtml(p.action_display)}<span class="sub">${escapeHtml(p.action_id)} · ${escapeHtml(p.action_label)}</span></td>
        <td>${Math.round(p.confidence * 100)}%${p.uncertain ? '<span class="tag-uncertain">불확실</span>' : ""}</td>
      </tr>`).join("");
    $("result-empty").hidden = rows.length > 0;
    $("result-empty").textContent = job.status === "FAILURE" ? "결과 없음 (실패 사유는 분석 상태를 확인하세요)"
      : job.status === "SUCCESS" ? "검출된 사람이 없습니다" : "분석이 끝나면 사람별 결과가 표시됩니다";
    $("result-message").textContent = rows.length ? `${rows.length}명 · Track ID는 이 영상 안에서만 유효한 번호입니다` : "";
    $("result-time").textContent = job.processing_ms ? `AI 처리 ${(job.processing_ms / 1000).toFixed(1)}초` : "";
    if (job.result_image) showImage(job.result_image, `작업 #${job.id} 분석 결과 (Skeleton)`);
  }

  function render(job) {
    renderStepper(job);
    renderResults(job);
  }

  async function poll(jobId) {
    clearTimeout(pollTimer);
    try {
      const job = await api(`${apiBase}${jobId}/status/`);
      job.input_type = job.input_type || (mode === "ipwebcam" ? "ipwebcam" : "upload");
      render(job);
      if (job.status === "SUCCESS" || job.status === "FAILURE") {
        $("start-button").disabled = false;
        loadHistory();
        return;
      }
    } catch (error) {
      $("status-text").textContent = `상태 조회 실패: ${error.message} (다시 시도 중)`;
    }
    pollTimer = setTimeout(() => poll(jobId), POLL_MS);
  }

  // ---------------- 분석 시작 ----------------
  $("start-button").addEventListener("click", async () => {
    const form = new FormData();
    form.append("input_type", mode);
    form.append("expected_action", $("expected-action").value);
    form.append("title", $("job-title").value.trim());
    if (mode === "upload") {
      if (!selectedFile) { alert("분석할 영상을 먼저 선택하세요."); return; }
      form.append("video", selectedFile);
    } else {
      if (!$("camera-key").value) { alert("허용된 카메라가 없습니다."); return; }
      form.append("camera_key", $("camera-key").value);
      stopSnapshot(); // 수집 중에는 미리보기 요청을 멈춰 카메라 부하를 줄인다.
      showPlaceholder(`카메라 앞에서 동작을 수행하세요 (${captureSeconds}초 수집)`);
    }

    // 이전 작업의 단계·결과·미리보기를 지우고 새 작업 표시를 시작한다.
    clearTimeout(pollTimer);
    render({ id: "-", status: "PENDING", status_display: "등록 중", stage: "queued", predictions: [] });
    if (mode === "upload") showVideo(localVideoUrl);
    $("job-label").textContent = "";
    $("start-button").disabled = true;
    $("status-text").classList.remove("error");
    $("status-text").textContent = "작업을 등록하는 중…";
    try {
      const job = await api(apiBase, { method: "POST", body: form });
      currentJobId = job.id;
      render(job);
      loadHistory();
      poll(job.id);
    } catch (error) {
      $("start-button").disabled = false;
      $("status-text").classList.add("error");
      $("status-text").textContent = `요청 실패: ${error.message}`;
      if (mode === "ipwebcam") startSnapshot();
    }
  });

  // ---------------- 최근 이력 (Read / Update / Delete) ----------------
  function fmtTime(value) {
    if (!value) return "";
    const d = new Date(value);
    return `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  async function loadHistory() {
    try {
      const data = await api(apiBase);
      const jobs = data.results || data;
      $("history-body").innerHTML = jobs.length ? jobs.map((job) => {
        const summary = (job.predictions || []).map((p) =>
          `ID${p.track_id} ${escapeHtml(p.action_display)} ${Math.round(p.confidence * 100)}%${p.uncertain ? "?" : ""}`).join(", ");
        const expected = job.expected_action ? (document.querySelector(`#expected-action option[value="${job.expected_action}"]`)?.textContent || job.expected_action) : "-";
        return `<tr data-id="${job.id}" class="${job.id === currentJobId ? "selected" : ""}" style="cursor:pointer">
          <td><b>#${String(job.id).padStart(3, "0")}</b></td>
          <td>${escapeHtml(job.title) || "-"}${job.memo ? `<div style="color:#6b6f86;font-size:12px">${escapeHtml(job.memo)}</div>` : ""}</td>
          <td>${escapeHtml(job.input_type_display)}${job.camera_name ? ` · ${escapeHtml(job.camera_name)}` : ""}</td>
          <td>${escapeHtml(expected)}</td>
          <td>${summary || (job.status === "FAILURE" ? `<span style="color:#db5a4b">${escapeHtml((job.error_message || "").slice(0, 40))}</span>` : "-")}</td>
          <td>${job.processing_ms ? (job.processing_ms / 1000).toFixed(1) + "초" : "-"}</td>
          <td><span class="pill ${job.status}">${escapeHtml(job.status_display)}</span></td>
          <td>${fmtTime(job.created_at)}</td>
          <td style="white-space:nowrap">
            <button class="btn" data-edit="${job.id}" type="button">메모</button>
            <button class="btn danger" data-delete="${job.id}" type="button">삭제</button>
          </td></tr>`;
      }).join("") : '<tr><td colspan="9">아직 분석 기록이 없습니다.</td></tr>';
    } catch (error) {
      $("history-body").innerHTML = `<tr><td colspan="9">이력을 불러오지 못했습니다: ${escapeHtml(error.message)}</td></tr>`;
    }
  }

  $("history-body").addEventListener("click", async (event) => {
    const editId = event.target.dataset.edit;
    const deleteId = event.target.dataset.delete;
    if (editId) {
      const job = await api(`${apiBase}${editId}/`);
      const title = prompt("제목", job.title);
      if (title === null) return;
      const memo = prompt("메모", job.memo);
      if (memo === null) return;
      await api(`${apiBase}${editId}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, memo }) });
      loadHistory();
      return;
    }
    if (deleteId) {
      if (!confirm(`작업 #${deleteId}와 사람별 결과, 영상 파일을 삭제할까요?`)) return;
      await api(`${apiBase}${deleteId}/`, { method: "DELETE" });
      if (String(currentJobId) === deleteId) currentJobId = null;
      loadHistory();
      return;
    }
    const row = event.target.closest("tr[data-id]");
    if (row) {
      currentJobId = Number(row.dataset.id);
      const job = await api(`${apiBase}${row.dataset.id}/`);
      render(job);
      if (!job.result_image && job.video) showVideo(job.video);
      if (job.status !== "SUCCESS" && job.status !== "FAILURE") poll(job.id);
      loadHistory();
    }
  });

  setMode("upload");
  loadHistory();
})();
