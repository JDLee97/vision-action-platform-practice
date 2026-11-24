// 관리자 대시보드: Django가 ORM으로 집계해 json_script로 넘긴 숫자로 Chart.js 차트 2개를 그린다.
(() => {
  const data = JSON.parse(document.getElementById("chart-data").textContent);
  const STATUS_COLORS = { 완료: "#2e9d4f", 실패: "#db5a4b", "처리 중": "#3d7df2", 대기: "#9a9db0" };
  const STATUS_KEYS = { SUCCESS: "완료", FAILURE: "실패", STARTED: "처리 중", PENDING: "대기" };

  document.querySelectorAll(".legend .sw").forEach((el) => {
    el.style.background = STATUS_COLORS[STATUS_KEYS[el.dataset.status]];
  });

  if (!window.Chart) {
    document.querySelectorAll(".chart-box").forEach((box) => {
      box.textContent = "Chart.js를 불러오지 못했습니다(인터넷 연결 확인). 숫자는 아래 표와 범례를 참고하세요.";
    });
    return;
  }
  Chart.defaults.font.family = '"Noto Sans KR", "Malgun Gothic", sans-serif';

  // ① 6개 Action별 예측 건수 — 가로 막대
  new Chart(document.getElementById("action-chart"), {
    type: "bar",
    data: {
      labels: data.actions.labels,
      datasets: [{ data: data.actions.counts, backgroundColor: "#3b40d6", borderRadius: 3, barThickness: 22 }],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.raw}건` } } },
      scales: {
        x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef0f7" } },
        y: { grid: { display: false }, ticks: { font: { size: 14 } } },
      },
    },
  });

  // ② 작업 상태별 건수 — 도넛 (가운데 총 건수)
  const total = data.statuses.counts.reduce((a, b) => a + b, 0);
  const centerText = {
    id: "centerText",
    afterDraw(chart) {
      const { ctx, chartArea } = chart;
      const x = (chartArea.left + chartArea.right) / 2;
      const y = (chartArea.top + chartArea.bottom) / 2;
      ctx.save();
      ctx.font = '700 24px "Noto Sans KR", sans-serif';
      ctx.fillStyle = "#1c1f33";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`총 ${total}건`, x, y);
      ctx.restore();
    },
  };
  new Chart(document.getElementById("status-chart"), {
    type: "doughnut",
    data: {
      labels: data.statuses.labels,
      datasets: [{
        data: total ? data.statuses.counts : [1],
        backgroundColor: total ? data.statuses.labels.map((l) => STATUS_COLORS[l]) : ["#e4e5ee"],
        borderWidth: 2,
      }],
    },
    options: {
      maintainAspectRatio: false,
      cutout: "58%",
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: total > 0,
          callbacks: { label: (c) => `${c.label} ${c.raw}건 (${Math.round((c.raw / total) * 100)}%)` },
        },
      },
    },
    plugins: [centerText],
  });
})();
