const $ = (selector) => document.querySelector(selector);
const UNIFIED_TOKEN_KEY = "suat_access_token";

function captureUnifiedTokenFromUrl() {
  const keys = ["access_token", "token", "accessToken"];
  const read = (params) => keys.map((key) => params.get(key)).find(Boolean) || "";
  const hash = location.hash.replace(/^#/, "");
  const token = (hash ? read(new URLSearchParams(hash)) : "") || read(new URLSearchParams(location.search));
  if (!token) return "";
  localStorage.setItem(UNIFIED_TOKEN_KEY, token);
  const params = new URLSearchParams(location.search);
  keys.forEach((key) => params.delete(key));
  const query = params.toString();
  history.replaceState(null, "", location.pathname + (query ? `?${query}` : ""));
  return token;
}

function unifiedToken() {
  return localStorage.getItem(UNIFIED_TOKEN_KEY) || "";
}

function unifiedLoginUrl() {
  const base = location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:3000"
    : "https://ai.ms1001.com";
  const url = new URL("/login", base);
  url.searchParams.set("redirect", location.href);
  return url.toString();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  const text = String(value || "").trim();
  return text ? text.replace("T", " ").slice(0, 16) : "未记录";
}

function statusText(status) {
  return { diagnosed: "已拆解", review_needed: "需复核", training: "训练中", passed: "已过关" }[status] || status || "已记录";
}

function renderRank(root, rows, field) {
  if (!rows || !rows.length) {
    root.innerHTML = `<div class="empty">暂无数据</div>`;
    return;
  }
  root.innerHTML = rows.map((row) => `<div class="rank-row"><span>${escapeHtml(row[field] || row.name || row.label)}</span><strong>${escapeHtml(row.count || 0)}</strong></div>`).join("");
}

async function loadShare() {
  const token = new URLSearchParams(location.search).get("token") || "";
  if (!token) throw new Error("缺少共享 token");
  const res = await fetch(`/api/share/${encodeURIComponent(token)}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "共享链接不可用");
  return data;
}

function renderShare(data) {
  const share = data.share || {};
  const student = data.student || {};
  const summary = data.summary || {};
  $("#shareTitle").textContent = share.title || "学习状态共享";
  $("#shareMeta").textContent = `${student.display_name || "学习者"} · ${share.audience || "家教/家长/教务"} · 生成于 ${formatDate(data.generated_at)}`;
  $("#summaryCards").innerHTML = `
    <article><span>错题总数</span><strong>${summary.total_wrong_questions || 0}</strong></article>
    <article><span>已过关</span><strong>${summary.passed_questions || 0}</strong></article>
    <article><span>过关率</span><strong>${summary.pass_rate || 0}%</strong></article>
    <article><span>覆盖学科</span><strong>${summary.subject_count || 0}</strong></article>
  `;
  const subjects = data.subjects || [];
  $("#subjectGrid").innerHTML = subjects.length ? subjects.map((item) => `
    <article class="subject-card">
      <span>${escapeHtml(item.name || "未识别学科")}</span>
      <strong>${escapeHtml(item.count || 0)} 题</strong>
      <p>已过关 ${escapeHtml(item.passed || 0)} · 过关率 ${escapeHtml(item.pass_rate || 0)}%</p>
    </article>
  `).join("") : `<div class="empty">暂无分科档案</div>`;
  renderRank($("#weakList"), data.report?.weak_mothers || [], "name");
  renderRank($("#errorList"), data.report?.error_causes || [], "label");
  const questions = data.recent_questions || [];
  $("#questionList").innerHTML = questions.length ? questions.map((item) => `
    <article class="question-card">
      <div><span class="tag">${escapeHtml(item.subject || "未识别")}</span><span class="tag muted">${escapeHtml(statusText(item.status))}</span></div>
      <h3>${escapeHtml(item.title || "题目档案")}</h3>
      <p>${escapeHtml(item.question || "")}</p>
      <small>${formatDate(item.created_at)} · ${escapeHtml(item.variants || 0)} 道同类题</small>
    </article>
  `).join("") : `<div class="empty">暂无近期题目</div>`;
  const history = data.history || [];
  $("#historyList").innerHTML = history.length ? history.map((item) => `
    <article class="history-card">
      <span class="tag muted">${escapeHtml(item.label || item.type)}</span>
      <strong>${escapeHtml(item.title || "生成记录")}</strong>
      <p>${escapeHtml(item.summary || "")}</p>
      <small>${formatDate(item.created_at)}</small>
    </article>
  `).join("") : `<div class="empty">暂无生成记录</div>`;
}

loadShare = async function loadShareWithUnifiedAuth() {
  captureUnifiedTokenFromUrl();
  const token = new URLSearchParams(location.search).get("token") || "";
  if (!token) throw new Error("缺少共享 token");
  const headers = {};
  const authToken = unifiedToken();
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  const res = await fetch(`/api/share/${encodeURIComponent(token)}`, { headers });
  const data = await res.json();
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error(`${data.error || "该共享链接需要登录后查看"}\n${unifiedLoginUrl()}`);
    }
    throw new Error(data.error || "共享链接不可用");
  }
  return data;
};

loadShare()
  .then((data) => {
    renderShare(data);
    $("#shareContent").classList.remove("hidden");
  })
  .catch((err) => {
    const [message, loginUrl] = String(err.message || "").split("\n");
    $("#shareError").innerHTML = loginUrl
      ? `${escapeHtml(message)}<br><a href="${escapeHtml(loginUrl)}">前往统一登录</a>`
      : escapeHtml(message);
    $("#shareError").classList.remove("hidden");
  });
