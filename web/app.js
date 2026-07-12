const state = {
  imageDataUrl: "",
  ocrText: "",
  ocrConfidence: 1,
  currentWrong: null,
  variants: [],
  models: [],
  imageModels: [],
  prompts: [],
  profile: { subjects: [], items: [] },
  profileShares: [],
  selectedModelId: "",
  selectedImageModelId: "",
  inputMode: "image",
  portalTools: [],
  activeToolId: "wrong-transfer",
  authMode: "login",
  user: null,
  history: { items: [], counts: {}, total: 0 },
  historyFilter: "all",
  agentLayers: [],
  agentRun: null,
  agentResult: null,
  ragDocuments: [],
  ragHits: [],
  studentMode: true,
  papers: [],
  workMode: localStorage.getItem("edu-work-mode") === "teacher" ? "teacher" : "student",
  activePaper: null,
  paperPollTimer: null,
  appConfig: { use_unified_auth: true, unified_auth_url: "https://ai.ms1001.com", platform_id: "edu.ms1001.com", local_auth_enabled: true },
};

const GUEST_WRONG_KEY = "gaokao_guest_wrong_ids";
const STUDENT_MODE_KEY = "gaokao_student_mode";
const PASS_REQUIRED_CORRECT = 2;
const UNIFIED_TOKEN_KEY = "suat_access_token";
const LOCAL_TOKEN_KEY = "gaokao_token";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const FILE_ACCEPT = ".pdf,.docx,.txt,.md,.csv,.json,image/*";

const PAPER_STATE_LABELS = { correct:"正确", wrong:"错误", partial:"部分正确", blank:"空白", review_required:"需复核" };

function prepareChineseWorkbench() {
  document.documentElement.lang = "zh-CN";
  document.title = "错题拆博士｜学生与教师学习工作台";
  const brand = $(".brand");
  if (brand) brand.innerHTML = `<div class="mark">博</div><div><strong>错题拆博士</strong><span>让每一道错题都有结果</span></div>`;
  const nav = $(".nav");
  if (nav) nav.innerHTML = `
    <button class="nav-item active" data-view="portal"><span class="nav-icon">首</span><span data-nav-label>学习首页</span></button>
    <button class="nav-item nav-core" data-view="paper"><span class="nav-icon">卷</span><span data-nav-label>试卷分析</span></button>
    <button class="nav-item nav-core" data-view="diagnose"><span class="nav-icon">题</span><span data-nav-label>错题分析</span></button>
    <button class="nav-item" data-view="library"><span class="nav-icon">本</span><span data-nav-label>我的错题本</span></button>
    <button class="nav-item" data-view="report"><span class="nav-icon">报</span><span data-nav-label>学习报告</span></button>
    <button class="nav-item" data-view="history"><span class="nav-icon">史</span><span data-nav-label>历史记录</span></button>
    <button class="nav-item" data-view="tool"><span class="nav-icon">工</span><span data-nav-label>20个工作台</span></button>
    <button class="nav-item hidden" id="adminNavItem" data-view="admin"><span class="nav-icon">管</span><span>后台管理</span></button>`;
  if (nav) nav.insertAdjacentHTML("afterend", `<section class="sidebar-account" aria-label="个人账号">
    <div class="sidebar-account-head"><span class="sidebar-avatar">我</span><div><strong id="sidebarAccountName">个人账号</strong><small id="sidebarAccountState">尚未登录</small></div></div>
    <button id="sidebarLoginBtn" class="sidebar-action primary" type="button">登录 / 注册</button>
  </section>`);
  const topTitle = $(".topbar h1"); if (topTitle) topTitle.textContent = "错题学习工作台";
  const topEyebrow = $(".topbar .eyebrow"); if (topEyebrow) topEyebrow.textContent = "学生 · 教师共用";
  const topSub = $(".topbar-subtitle"); if (topSub) topSub.textContent = "整卷识别、八步拆题、巩固训练、间隔复习与学习档案";
  const topbar = $(".topbar");
  if (topbar) topbar.insertAdjacentHTML("beforeend", `<div class="workspace-account"><span id="workspaceAccountText">尚未登录</span><button id="workspaceLoginBtn" class="primary-btn" type="button">登录 / 注册</button></div>`);
  $(".tech-ribbon")?.remove();
  $(".student-mode-toggle")?.remove();
  $(".side-note")?.remove();
  const institution = $(".institution-entry");
  if (institution) institution.innerHTML = `<a href="/org" class="primary-btn">机构工作台</a><a href="/org-admin" class="ghost-btn">机构管理</a>`;
  $(".portal-tools-panel")?.removeAttribute("data-student-hide");
  const main = $(".main");
  const paperWorkbench = $("#paperWorkbench");
  if (main && paperWorkbench && !$("#view-paper")) {
    const paperView = document.createElement("section");
    paperView.id = "view-paper"; paperView.className = "view";
    paperView.innerHTML = `<section class="panel split-view-intro"><p class="eyebrow">整卷识别</p><h2>试卷分析工作台</h2><p>上传完整试卷，逐题识别印刷内容、学生笔迹和教师批改，再生成全卷报告。</p></section>`;
    paperView.appendChild(paperWorkbench);
    main.appendChild(paperView);
  }
  const toolPanel = $(".portal-tools-panel"), dashboard = $("#dualDashboard");
  if (toolPanel && dashboard) {
    toolPanel.classList.add("home-tool-matrix");
    dashboard.insertAdjacentElement("afterend", toolPanel);
    const heading = toolPanel.querySelector("h2"); if (heading) heading.textContent = "全部22个学习与教学功能";
  }
  applyWorkMode(state.workMode);
}

function applyWorkMode(mode) {
  state.workMode = mode === "teacher" ? "teacher" : "student";
  localStorage.setItem("edu-work-mode", state.workMode);
  document.body.dataset.workMode = state.workMode;
  $$('[data-work-mode]').forEach(btn => btn.classList.toggle("is-active", btn.dataset.workMode === state.workMode));
  $("#studentDashboardActions")?.classList.toggle("hidden", state.workMode !== "student");
  $("#teacherDashboardActions")?.classList.toggle("hidden", state.workMode !== "teacher");
  const teacher = state.workMode === "teacher";
  if ($("#dashboardKicker")) $("#dashboardKicker").textContent = teacher ? "今天需要处理什么？" : "今天从哪一步开始？";
  if ($("#dashboardTitle")) $("#dashboardTitle").textContent = teacher ? "从一张试卷，看清每个学生的问题" : "把不会的题，真正练到会";
  if ($("#dashboardLead")) $("#dashboardLead").textContent = teacher ? "批量分析试卷、复核识别结果、查看知识点失分，并导出可交付的教学报告。" : "上传整张试卷或一道错题，识别笔迹、定位错因、八步讲解，再进入巩固和复习。";
  const labels = teacher
    ? ["教学首页","试卷分析","错题分析","学生错题库","学情报告","历史记录","22个工作台"]
    : ["学习首页","试卷分析","错题分析","我的错题本","学习报告","历史记录","22个工作台"];
  $$(".nav-item [data-nav-label]").forEach((node,index) => { if (labels[index]) node.textContent=labels[index]; });
  loadDashboard().catch(() => {});
}

async function loadDashboard() {
  const [papers, wrongs] = await Promise.all([api("/api/papers"), fetchWrongQuestions()]);
  state.papers = papers;
  const now=Date.now();
  const due=wrongs.filter(x=>x.workflow_state==="review_scheduled"&&x.next_review_at&&Date.parse(x.next_review_at)<=now);
  const review=wrongs.filter(x=>x.status==="review_needed"||x.status==="remediation");
  const mastered=wrongs.filter(x=>x.status==="passed"||x.workflow_state==="mastered");
  $("#dashDueCount").textContent=due.length; $("#dashReviewCount").textContent=review.length; $("#dashMasteredCount").textContent=mastered.length; $("#dashPaperCount").textContent=papers.length;
  const recent=$("#dashboardRecentList"); if (!recent) return;
  const paperRows=papers.slice(0,3).map(p=>`<button type="button" data-recent-paper="${p.id}"><span class="recent-mark">卷</span><span><strong>${escapeHtml(p.title)}</strong><small>${escapeHtml(p.created_at||"")} · ${p.status==="completed"?"分析完成":p.status==="failed"?"分析失败":"正在分析"}</small></span><b>查看</b></button>`);
  const wrongRows=wrongs.slice(0,3).map(w=>`<button type="button" data-recent-wrong="${w.id}"><span class="recent-mark">题</span><span><strong>${escapeHtml(w.diagnosis?.core_pattern||"错题分析")}</strong><small>${escapeHtml(subjectOf(w))} · ${statusText(w.status)}</small></span><b>继续</b></button>`);
  recent.innerHTML=[...paperRows,...wrongRows].join("")||`<div class="dashboard-empty"><strong>还没有学习记录</strong><p>上传一张试卷或一道错题，开始第一次分析。</p></div>`;
  recent.querySelectorAll("[data-recent-paper]").forEach(btn=>btn.addEventListener("click",async()=>{switchView("diagnose");const p=await api(`/api/papers/${btn.dataset.recentPaper}`);renderPaperResult(p);}));
  recent.querySelectorAll("[data-recent-wrong]").forEach(btn=>btn.addEventListener("click",async()=>{switchView("diagnose");renderDiagnosis(await api(`/api/wrong-questions/${btn.dataset.recentWrong}`));}));
}

function bindDashboard() {
  $$('[data-work-mode]').forEach(btn=>btn.addEventListener("click",()=>applyWorkMode(btn.dataset.workMode)));
  $("#dashboardRefreshBtn")?.addEventListener("click",()=>loadDashboard().catch(err=>toast(err.message)));
  $("#paperFilesInput")?.addEventListener("change", updatePaperSelection);
  $("#workspaceLoginBtn")?.addEventListener("click",()=>state.appConfig.use_unified_auth?goUnifiedLogin("login"):openModal("authModal"));
  $("#sidebarLoginBtn")?.addEventListener("click",()=>state.user?logoutPersonalAccount():goUnifiedLogin("login"));
  $$('[data-dashboard-action]').forEach(btn=>btn.addEventListener("click",()=>{
    const action=btn.dataset.dashboardAction;
    if (action === "paper") { switchView("paper"); setTimeout(()=>$("#paperWorkbench")?.scrollIntoView({behavior:"smooth"}),50); }
    else if (["single","review"].includes(action)) { switchView("diagnose"); setTimeout(()=>$(".upload-panel")?.scrollIntoView({behavior:"smooth"}),50); }
    else if (action==="library"||action==="today") switchView(action==="library"?"library":"portal");
    else if (action==="report") switchView("report"); else if (action==="profile") switchView("profile");
  }));
}

function logoutPersonalAccount(){ clearToken(); state.user=null; updateAccountCard(); toast("已退出登录。"); }

async function createPaperAnalysis() {
  const files = Array.from($("#paperFilesInput")?.files || []);
  const paperText = $("#paperTextInput")?.value.trim() || "";
  if (!files.length && !paperText) { toast("请上传试卷图片或粘贴整卷文本。"); return; }
  const pages = [];
  for (const file of files) {
    if (file.type.startsWith("image/")) pages.push({ image_data_url: await readFileAsDataUrl(file), name:file.name });
    else pages.push({ text: await file.text(), name:file.name });
  }
  renderPaperJob({ status:"uploading", progress:1, title:"正在上传并读取试卷" });
  const done = setBusy($("#analyzePaperBtn"), "正在上传...");
  try {
    const result = await api("/api/papers", { method:"POST", body:JSON.stringify({
      title: $("#paperTitleInput")?.value.trim() || files[0]?.name || "未命名试卷",
      subject: $("#paperSubjectSelect")?.value || "自动识别",
      source_name: files.map(f => f.name).join("、"), pages,
      paper_text: paperText || undefined, model_id:selectedModelId(),
    }) });
    renderPaperJob({ status:"queued", progress:0, title:"全卷任务已创建" });
    pollPaper(result.id);
    await loadPapers();
  } catch (err) { toast(err.message); } finally { done(); }
}

function renderPaperJob(paper) {
  const root = $("#paperJobStatus"); if (!root) return;
  root.classList.remove("hidden");
  const labels={uploading:"正在上传",queued:"等待识别",processing:Number(paper.progress||0)<46?"正在识别题目和笔迹":"正在逐题分析",completed:"分析完成",failed:"分析失败"};
  root.innerHTML = `<div><strong>${escapeHtml(paper.title || "全卷分析")}</strong><span><i class="recognition-spinner" aria-hidden="true"></i>${labels[paper.status]||"正在处理"} · ${Number(paper.progress || 0)}%</span></div><div class="paper-progress"><i style="width:${Number(paper.progress || 0)}%"></i></div><p class="paper-status-tip">${paper.status==="failed"?"请查看失败原因并重试。":"请保持页面打开；任务完成后会自动显示逐题结果。"}</p>${paper.error ? `<p class="text-error">失败原因：${escapeHtml(paper.error)}</p>` : ""}`;
}

function updatePaperSelection() {
  const files=Array.from($("#paperFilesInput")?.files||[]); const root=$("#paperSelectedFiles"); if(!root)return;
  root.innerHTML=files.length?`<strong>已选择 ${files.length} 个文件</strong>${files.map(f=>`<span>${escapeHtml(f.name)} · ${Math.max(1,Math.round(f.size/1024))} KB</span>`).join("")}`:`<span>尚未选择文件</span>`;
  if(files.length&&!$("#paperTitleInput").value.trim()) $("#paperTitleInput").value=files[0].name.replace(/\.[^.]+$/,"");
}

async function pollPaper(id) {
  clearTimeout(state.paperPollTimer);
  try {
    const paper = await api(`/api/papers/${id}`); renderPaperJob(paper);
    if (paper.status === "completed") { state.activePaper = paper; renderPaperResult(paper); await loadPapers(); toast("全卷分析完成。"); return; }
    if (paper.status === "failed") { await loadPapers(); return; }
    state.paperPollTimer = setTimeout(() => pollPaper(id), 1800);
  } catch (err) { toast(err.message); }
}

async function loadPapers() {
  state.papers = await api("/api/papers");
  const root = $("#paperHistoryList"); if (!root) return;
  root.innerHTML = state.papers.length ? state.papers.map(p => `<article class="paper-history-card" data-paper-id="${p.id}"><div><strong>${escapeHtml(p.title)}</strong><span>${escapeHtml(p.created_at || "")} · ${escapeHtml(p.status)} · ${Number(p.progress || 0)}%</span></div><div><button class="ghost-btn paper-open" type="button">查看</button>${p.status === "failed" ? '<button class="ghost-btn paper-retry" type="button">重试</button>' : ""}</div></article>`).join("") : `<div class="empty-state compact-empty"><p>还没有全卷分析记录。</p></div>`;
  root.querySelectorAll(".paper-open").forEach(btn => btn.addEventListener("click", async () => { const card=btn.closest("[data-paper-id]"); const paper=await api(`/api/papers/${card.dataset.paperId}`); state.activePaper=paper; renderPaperResult(paper); if (!["completed","failed"].includes(paper.status)) pollPaper(paper.id); }));
  root.querySelectorAll(".paper-retry").forEach(btn => btn.addEventListener("click", async () => { const id=btn.closest("[data-paper-id]").dataset.paperId; await api(`/api/papers/${id}/retry`,{method:"POST",body:"{}"}); pollPaper(id); }));
}

function renderMemoryPoem(poem) {
  if (!poem?.lines?.length) return "";
  return `<section class="memory-poem"><div><span>题后一诗 · 暗藏解题模型</span><h4>${escapeHtml(poem.title || "解题记忆诗")}</h4></div><div class="memory-poem-lines">${poem.lines.map((line,index)=>`<p><b>${String(index+1).padStart(2,"0")}</b>${escapeHtml(line)}</p>`).join("")}</div><details><summary>展开诗句里的解题步骤</summary>${(poem.line_reviews||[]).map(item=>`<p><strong>${escapeHtml(item.model_hint||"模型提示")}</strong>${escapeHtml(item.line||"")}</p>`).join("")}</details><small>${escapeHtml(poem.purpose||"")}</small></section>`;
}

function renderPaperResult(paper) {
  const root = $("#paperResult"); if (!root) return; root.classList.remove("hidden");
  const summary = paper.summary || {};
  root.innerHTML = `<div class="paper-result-head"><div><p class="eyebrow">高考全卷复盘</p><h3>${escapeHtml(paper.title)}</h3><p>共 ${summary.total_questions || 0} 题 · 错题/待复核 ${summary.wrong_count || 0} · 母题命中 ${summary.mother_matched_count || 0} · 知识卡 ${summary.knowledge_card_count || 0}</p></div><div><button class="ghost-btn" data-export="docx">导出 Word</button><button class="primary-btn" data-export="pdf">导出 PDF</button></div></div><div class="paper-question-list">${(paper.questions || []).map(q => { const card=q.diagnosis?.gaokao_card; const mother=card?.mother_match; return `<article class="paper-question ${q.answer_state}"><div class="paper-question-head"><strong>第 ${escapeHtml(q.question_no)} 题</strong><span class="tag">${PAPER_STATE_LABELS[q.answer_state] || q.answer_state}</span></div><p>${escapeHtml(q.printed_text)}</p>${mother?`<div class="mother-match"><b>${escapeHtml(mother.code)} · ${escapeHtml(mother.name)}</b><span>${escapeHtml(mother.formula)}</span><small>${escapeHtml(mother.source)}</small></div>`:`<div class="mother-match review"><b>母题待教研复核</b><span>当前不会伪造真题来源，确认后再沉淀。</span></div>`}${q.student_work ? `<div class="paper-evidence"><b>学生笔迹/作答</b>${escapeHtml(q.student_work)}</div>`:""}${q.teacher_marks ? `<div class="paper-evidence"><b>教师批改</b>${escapeHtml(q.teacher_marks)}</div>`:""}${card?.steps?.length ? `<div class="eight-step-grid gaokao-card-grid">${card.steps.map(s=>`<section><span>${s.number}</span><strong>${escapeHtml(s.label)}</strong><p>${escapeHtml(typeof s.content==="string"?s.content:JSON.stringify(s.content))}</p></section>`).join("")}</div>`:(q.eight_steps?.length ? `<div class="eight-step-grid">${q.eight_steps.map(s=>`<section><span>${s.number}</span><strong>${escapeHtml(s.label)}</strong><p>${escapeHtml(s.content || "待复核")}</p></section>`).join("")}</div>`:"")}${renderMemoryPoem(card?.memory_poem || q.diagnosis?.poem)}</article>`; }).join("")}</div>`;
  root.querySelectorAll("[data-export]").forEach(btn => btn.addEventListener("click", () => downloadPaper(paper.id, btn.dataset.export)));
  root.scrollIntoView({behavior:"smooth",block:"start"});
}

async function downloadPaper(id, format) {
  const headers = {}; const token = getToken(); if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/api/papers/${id}/export/${format}`, {headers});
  if (!response.ok) throw new Error((await response.json()).error || "导出失败");
  const blob = await response.blob(); const url=URL.createObjectURL(blob); const a=document.createElement("a"); a.href=url; a.download=`全卷分析.${format}`; a.click(); URL.revokeObjectURL(url);
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("文件读取失败"));
    reader.readAsDataURL(file);
  });
}

function appendExtractedText(textarea, text, filename) {
  const block = `\n\n--- 来自文件：${filename} ---\n${text}\n`;
  textarea.value = textarea.value.trim() ? `${textarea.value.trim()}${block}` : text;
}

function sensitiveUploadReason(text) {
  const content = String(text || "").replace(/\s+/g, " ");
  const signals = [
    /居民身份证|公民身份号码|身份证号|出生\s*\d{4}年|民族\s*[\u4e00-\u9fff]+|住址\s*[\u4e00-\u9fff]/,
    /\b\d{17}[0-9Xx]\b/,
    /\b1[3-9]\d{9}\b/,
    /姓名\s*[\u4e00-\u9fff]{2,4}\s*[;；,，]?\s*性别/,
  ];
  if (signals.some((pattern) => pattern.test(content))) {
    return "疑似个人身份信息，已拦截，未写入题目框";
  }
  return "";
}


async function ingestFileIntoTextarea(file, textarea, options = {}) {
  const allowOcr = options.allowOcr !== false;
  const answerTextarea = options.answerTextarea || null;
  if (file.size > 25 * 1024 * 1024) {
    throw new Error("文件不能超过 25MB");
  }
  const dataUrl = await readFileAsDataUrl(file);
  if (allowOcr && file.type.startsWith("image/")) {
    const result = await api("/api/ocr", {
      method: "POST",
      body: JSON.stringify({ image_data_url: dataUrl, model_id: selectedModelId() }),
    });
    const questionText = result.printed_question || result.ocr_text || "";
    const answerText = [result.student_work, result.teacher_marks].filter(Boolean).join("\n");
    const combinedText = [questionText, answerText, result.teacher_marks, result.ocr_text].filter(Boolean).join("\n");
    const blockedReason = sensitiveUploadReason(combinedText);
    if (blockedReason) {
      return { kind: "blocked", chars: 0, answerChars: 0, reason: blockedReason };
    }
    appendExtractedText(textarea, questionText, file.name);
    if (answerTextarea && answerText) appendExtractedText(answerTextarea, answerText, `${file.name} 作答/批注`);
    return { kind: "ocr", chars: (questionText || "").length, answerChars: answerText.length };
  }
  const result = await api("/api/extract-document", {
    method: "POST",
    body: JSON.stringify({ filename: file.name, file_data_url: dataUrl }),
  });
  appendExtractedText(textarea, result.text || "", file.name);
  return { kind: "document", chars: result.chars || (result.text || "").length };
}

function bindFileIngest(root) {
  if (!root || root.dataset.bound === "1") return;
  const targetId = root.dataset.target;
  const textarea = document.getElementById(targetId);
  if (!textarea) return;
  const answerTextarea = root.dataset.answerTarget ? document.getElementById(root.dataset.answerTarget) : null;
  root.dataset.bound = "1";
  const allowOcr = root.dataset.ocr !== "false";
  const input = root.querySelector(".file-ingest-input");
  const list = root.querySelector(".file-ingest-list");
  const dropzone = root.querySelector(".file-dropzone");
  if (!input || !dropzone) return;

  const addListItem = (name, state) => {
    if (!list) return null;
    const li = document.createElement("li");
    li.textContent = name;
    li.className = state;
    list.appendChild(li);
    return li;
  };

  const handleFiles = async (files) => {
    const batch = Array.from(files || []);
    if (!batch.length) return;
    for (const file of batch) {
      const item = addListItem(`${file.name} · 解析中…`, "");
      try {
        toast(`正在解析：${file.name}`);
        const meta = await ingestFileIntoTextarea(file, textarea, { allowOcr, answerTextarea });
        if (item) {
          if (meta.kind === "blocked") {
            item.textContent = `${file.name} · 已拦截`;
            item.title = meta.reason || "文件未写入输入框";
            item.className = "blocked";
          } else {
            item.textContent = `${file.name} · ${meta.kind === "ocr" ? "OCR" : "文档"} ${meta.chars} 字`;
            item.className = "done";
          }
        }
      } catch (err) {
        if (item) {
          item.textContent = `${file.name} · 未导入`;
          item.title = err.message;
          item.className = "error";
        }
        toast(`未导入：${err.message}`);
      }
    }
    toast("文件已写入输入框，请检查内容后提交。");
  };

  input.addEventListener("change", () => {
    handleFiles(input.files);
    input.value = "";
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", (event) => {
    handleFiles(event.dataTransfer?.files);
  });

  textarea.addEventListener("paste", async (event) => {
    const files = Array.from(event.clipboardData?.files || []);
    if (!files.length) return;
    event.preventDefault();
    await handleFiles(files);
  });
}

function bindAllFileIngests() {
  $$(".file-ingest").forEach((root) => bindFileIngest(root));
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 3200);
}

function captureUnifiedTokenFromUrl() {
  const keys = ["access_token", "token", "accessToken"];
  const read = (params) => keys.map((key) => params.get(key)).find(Boolean) || "";
  const hash = location.hash.replace(/^#/, "");
  const hashToken = hash ? read(new URLSearchParams(hash)) : "";
  const query = new URLSearchParams(location.search);
  const queryToken = read(query);
  const token = hashToken || queryToken;
  if (!token) return "";
  localStorage.setItem(UNIFIED_TOKEN_KEY, token);
  history.replaceState(null, "", location.pathname + (hashToken ? location.search : ""));
  return token;
}

function getUnifiedToken() {
  return localStorage.getItem(UNIFIED_TOKEN_KEY) || "";
}

function getToken() {
  return getUnifiedToken() || localStorage.getItem(LOCAL_TOKEN_KEY) || "";
}

function setToken(token) {
  localStorage.setItem(LOCAL_TOKEN_KEY, token);
}

function clearToken() {
  localStorage.removeItem(LOCAL_TOKEN_KEY);
  localStorage.removeItem(UNIFIED_TOKEN_KEY);
}

function unifiedAuthBase() {
  const configured = String(state.appConfig.unified_auth_url || "").replace(/\/$/, "");
  const fallback = location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:3000"
    : "https://ai.ms1001.com";
  return configured || fallback;
}

function unifiedLoginUrl(tab = "login", redirectUrl = location.href) {
  const url = new URL("/login", unifiedAuthBase());
  url.searchParams.set("redirect", redirectUrl);
  if (tab === "register") url.searchParams.set("tab", "register");
  return url.toString();
}

function goUnifiedLogin(tab = "login") {
  location.href = unifiedLoginUrl(tab, location.href);
}

async function loadAppConfig() {
  try {
    state.appConfig = await api("/api/config", { skipAuth: true });
  } catch {
    state.appConfig = { use_unified_auth: true, unified_auth_url: "https://ai.ms1001.com", platform_id: "edu.ms1001.com", local_auth_enabled: true };
  }
}

async function api(path, options = {}) {
  const { skipAuth = false, ...fetchOptions } = options;
  const headers = { "Content-Type": "application/json", ...(fetchOptions.headers || {}) };
  const token = skipAuth ? "" : getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, {
    ...fetchOptions,
    headers,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "请求失败");
  return data;
}

function setBusy(button, busyText) {
  const oldText = button.textContent;
  button.disabled = true;
  button.textContent = busyText;
  return () => {
    button.disabled = false;
    button.textContent = oldText;
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getGuestWrongIds() {
  try {
    return JSON.parse(localStorage.getItem(GUEST_WRONG_KEY) || "[]");
  } catch {
    return [];
  }
}

function rememberGuestWrong(id) {
  if (!id) return;
  const ids = getGuestWrongIds().filter((item) => item !== id);
  ids.unshift(id);
  localStorage.setItem(GUEST_WRONG_KEY, JSON.stringify(ids.slice(0, 50)));
}

function formatDate(value) {
  const text = String(value || "").trim();
  if (!text) return "未记录时间";
  return text.replace("T", " ").slice(0, 16);
}

function variantProgress(item) {
  const variants = item?.variants || [];
  if (!variants.length) return { done: 0, total: 0 };
  const done = variants.filter((variant) => (variant.answers || []).some((answer) => answer.is_correct)).length;
  return { done, total: variants.length };
}

function questionNeedsCalibration(text, confidence = state.ocrConfidence) {
  const content = String(text || "").trim();
  if (!content) return true;
  if (Number(confidence) < 0.8) return true;
  if (content.length < 12) return true;
  if ((content.match(/\?/g) || []).length >= 3) return true;
  if (/\bc03|c0s|AE1|、\/\d|\/5，c/i.test(content)) return true;
  return false;
}

function setCalibrationBanner(visible) {
  $("#ocrCalibrationBanner")?.classList.toggle("hidden", !visible);
}

function updateDiagnoseProgress(step) {
  const order = getStepOrder(step);
  $$("#diagnoseProgress .progress-step").forEach((node) => {
    const nodeOrder = getStepOrder(node.dataset.step);
    node.classList.toggle("active", node.dataset.step === step);
    node.classList.toggle("done", nodeOrder > 0 && nodeOrder < order);
  });
}

function getStepOrder(step) {
  return { input: 1, diagnose: 2, training: 3, archive: 4 }[step] || 0;
}

function applyStudentMode() {
  const enabled = Boolean(state.studentMode);
  document.body.classList.toggle("student-mode", enabled);
  localStorage.setItem(STUDENT_MODE_KEY, enabled ? "1" : "0");
  const toggle = $("#studentModeToggle");
  if (toggle) toggle.checked = enabled;
}

function typesetMath(root) {
  if (!root || typeof renderMathInElement !== "function") return;
  renderMathInElement(root, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "$", right: "$", display: false },
      { left: "\\(", right: "\\)", display: false },
      { left: "\\[", right: "\\]", display: true },
    ],
    throwOnError: false,
  });
}

async function fetchWrongQuestions() {
  if (state.user) return api("/api/wrong-questions");
  const ids = getGuestWrongIds();
  if (!ids.length) return [];
  return api(`/api/wrong-questions?ids=${encodeURIComponent(ids.join(","))}`);
}

function renderChips(container, items) {
  container.innerHTML = "";
  (items || []).forEach((item) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = item;
    container.appendChild(chip);
  });
}

function stackCard(title, body, foot = "") {
  return `
    <article class="stack-card">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(body)}</p>
      ${foot ? `<small>${escapeHtml(foot)}</small>` : ""}
    </article>
  `;
}

function setInputMode(mode) {
  state.inputMode = mode;
  $$(".input-mode").forEach((button) => {
    button.classList.toggle("active", button.dataset.inputMode === mode);
  });
  $("#imageInputBlock").classList.toggle("hidden", mode !== "image");
  $("#fileInputBlock").classList.toggle("hidden", mode !== "file");
  $("#pasteInputBlock").classList.toggle("hidden", mode !== "paste");
}


const TERMS = {
  service: {
    title: "用户服务协议",
    body: "本系统提供 AI 辅助学习、备课、出题、解析、复盘和图片生成等教育工具。生成内容仅供教学与学习参考，正式使用前请自行审核。用户应保证上传材料来源合法，不得上传侵犯他人权益或违法违规内容。",
  },
  privacy: {
    title: "隐私政策",
    body: "系统会保存账号、积分、生成历史、题目和必要配置，用于提供学习档案与历史追溯。请避免上传身份证号、住址、银行卡等非必要敏感信息。调用第三方模型时，必要材料可能发送至所配置的模型服务商。",
  },
  ai: {
    title: "AI生成内容免责声明",
    body: "AI 输出可能存在错误、不完整或不适用于特定考试地区、教材版本和评分标准的情况。题目、答案、解析、图片和计划均应由教师、学生或家长复核后使用。",
  },
};

function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
}

function updateAdminNav() {
  const adminNav = $("#adminNavItem");
  if (adminNav) adminNav.classList.toggle("hidden", !state.user?.is_admin);
}

function updateAccountCard() {
  const title = $("#accountTitle");
  const desc = $("#accountDesc");
  const actions = $("#accountActions");
  if (!title || !desc || !actions) return;
  updateAdminNav();
  if (state.user) {
    const role = state.user.is_admin ? "管理员" : "学员";
    title.textContent = `${state.user.email} · ${role} · ${state.user.credits || 0} 积分`;
    desc.textContent = state.user.is_admin
      ? "管理员账号可查看全部历史记录，并在「后台配置」中管理模型与提示词。"
      : "已登录。您的拆题、工具生成与学习卡片会保存到个人历史，与其他账号隔离。";
    actions.innerHTML = `
      <button class="ghost-btn" type="button" id="redeemOpenBtn">积分兑换</button>
      <button class="ghost-btn" type="button" id="logoutBtn">退出</button>
    `;
    $("#redeemOpenBtn")?.addEventListener("click", () => openModal("redeemModal"));
    $("#logoutBtn")?.addEventListener("click", () => {
      clearToken();
      state.user = null;
      updateAccountCard();
      toast("已退出登录。");
    });
    return;
  }
  title.textContent = "未登录 · 每个工具可先体验";
  desc.textContent = "注册后赠送 9 个本地演示积分，可兑换并保存生成成果。";
  actions.innerHTML = `<button class="primary-btn" type="button" id="openAuthBtn">登录 / 注册</button><button class="ghost-btn" type="button" id="openRedeemAnonBtn">积分兑换</button>`;
  $("#openAuthBtn")?.addEventListener("click", () => openModal("authModal"));
  $("#openRedeemAnonBtn")?.addEventListener("click", () => openModal("redeemModal"));
}

updateAccountCard = function updateAccountCardClean() {
  updateAdminNav();
  const workspaceText = $("#workspaceAccountText");
  const workspaceButton = $("#workspaceLoginBtn");
  if (workspaceText) workspaceText.textContent = state.user ? `${state.user.email || "已登录"}${state.user.is_admin ? " · 最高权限" : ""}` : "尚未登录";
  if (workspaceButton) {
    workspaceButton.textContent = state.user ? "退出登录" : "登录 / 注册";
    workspaceButton.onclick = state.user ? (()=>{clearToken();state.user=null;updateAccountCard();toast("已退出登录。");}) : (()=>state.appConfig.use_unified_auth?goUnifiedLogin("login"):openModal("authModal"));
  }
  const sidebarName = $("#sidebarAccountName");
  const sidebarState = $("#sidebarAccountState");
  const sidebarButton = $("#sidebarLoginBtn");
  if (sidebarName) sidebarName.textContent = state.user ? (state.user.email || "个人账号") : "个人账号";
  if (sidebarState) sidebarState.textContent = state.user ? `${state.user.is_admin ? "最高权限" : "已登录"} · ${state.user.credits || 0}积分` : "尚未登录";
  if (sidebarButton) sidebarButton.textContent = state.user ? "退出登录" : "登录 / 注册";
  const title = $("#accountTitle");
  const desc = $("#accountDesc");
  const actions = $("#accountActions");
  if (!title || !desc || !actions) return;
  if (state.user) {
    const role = state.user.is_admin ? "管理员" : "学员";
    title.textContent = `${state.user.email} · ${role} · ${state.user.credits || 0} 积分`;
    desc.textContent = state.user.is_admin
      ? "管理员账号可查看全部历史记录，并在后台配置中管理模型与提示词。"
      : "已登录。你的拆题、工具生成、学习卡片、档案和共享链接会保存到个人历史。";
    actions.innerHTML = `
      <button class="ghost-btn" type="button" id="redeemOpenBtn">积分兑换</button>
      <button class="ghost-btn" type="button" id="logoutBtn">退出</button>
    `;
    $("#redeemOpenBtn")?.addEventListener("click", () => openModal("redeemModal"));
    $("#logoutBtn")?.addEventListener("click", () => {
      clearToken();
      state.user = null;
      updateAccountCard();
      toast("已退出登录。");
    });
    return;
  }
  title.textContent = "未登录 · 可先体验，也可统一登录同步数据";
  desc.textContent = state.appConfig.use_unified_auth
    ? "接入 MS1001 统一认证后，可以和 Poster、家教网、会员中心共用同一个账号。"
    : "注册后赠送 9 个本地演示积分，可兑换并保存生成成果。";
  actions.innerHTML = `<button class="primary-btn" type="button" id="openUnifiedAuthBtn">统一登录 / 注册</button>`;
  $("#openUnifiedAuthBtn")?.addEventListener("click", () => goUnifiedLogin("login"));
  $("#openRedeemAnonBtn")?.addEventListener("click", () => openModal("redeemModal"));
};

async function loadUser() {
  if (!getToken()) {
    state.user = null;
    updateAccountCard();
    return;
  }
  try {
    state.user = await api("/api/me");
  } catch (err) {
    clearToken();
    state.user = null;
  }
  updateAccountCard();
}

function setAuthMode(mode) {
  state.authMode = mode;
  $$(".modal-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.authMode === mode));
  $("#authSubmitBtn").textContent = mode === "login" ? "登录" : "注册";
  $("#authHint").textContent = mode === "login" ? "登录后即可同步积分、兑换权益并保存生成历史。" : "注册后赠送 9 个本地演示积分，用来跑通工具站体验。";
}

async function submitAuth() {
  if (!$("#termsAgree")?.checked) {
    toast("请先阅读并同意相关条款。");
    return;
  }
  const button = $("#authSubmitBtn");
  const done = setBusy(button, state.authMode === "login" ? "登录中..." : "注册中...");
  try {
    const result = await api(state.authMode === "login" ? "/api/login" : "/api/register", {
      method: "POST",
      body: JSON.stringify({ email: $("#authEmail").value.trim(), password: $("#authPassword").value }),
    });
    setToken(result.token);
    state.user = result;
    closeModal("authModal");
    updateAccountCard();
    toast(state.authMode === "login" ? "登录成功。" : "注册成功，已赠送演示积分。");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

async function submitRedeem() {
  const button = $("#redeemSubmitBtn");
  const done = setBusy(button, "兑换中...");
  try {
    const result = await api("/api/redeem", {
      method: "POST",
      body: JSON.stringify({ code: $("#redeemCodeInput").value.trim() }),
    });
    if (state.user) state.user.credits = result.credits;
    closeModal("redeemModal");
    updateAccountCard();
    toast(`兑换成功，增加 ${result.added} 积分。`);
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

function showTerms(type) {
  const item = TERMS[type] || TERMS.service;
  $("#termsTitle").textContent = item.title;
  $("#termsContent").textContent = item.body;
  openModal("termsModal");
}

async function loadPortalTools() {
  state.portalTools = await api("/api/portal-tools");
  renderPortalTools();
  renderToolSelect();
}

function renderLatexDocument(source){
  const preview=$("#latexRenderPreview"); if(!preview)return;
  const body=String(source||"").replace(/[\s\S]*?\\begin\{document\}/," ").replace(/\\end\{document\}[\s\S]*/,"").replace(/\\maketitle/g,"");
  const chunks=body.split(/(\$\$[\s\S]*?\$\$|\$[^$]+\$)/g).filter(Boolean);
  preview.innerHTML=chunks.map(chunk=>{
    if(chunk.startsWith("$$")||chunk.startsWith("$")){
      const display=chunk.startsWith("$$"), math=chunk.slice(display?2:1,display?-2:-1);
      try{return window.katex?katex.renderToString(math,{displayMode:display,throwOnError:false,trust:false}):`<code>${escapeHtml(chunk)}</code>`;}catch{return `<code>${escapeHtml(chunk)}</code>`;}
    }
    return `<span>${escapeHtml(chunk.replace(/\\par/g,"\n").replace(/\\\\/g,"\n"))}</span>`;
  }).join("");
}

async function convertLatexInput(){
  const file=$("#latexFileInput")?.files?.[0], textValue=$("#latexPasteInput")?.value||"";
  if(!file&&!textValue.trim()){toast("请粘贴内容或选择文件。");return;}
  const button=$("#convertLatexBtn"), done=setBusy(button,"正在转换...");
  try{
    const payload=file?{filename:file.name,data_url:await readFileAsDataUrl(file),model_id:selectedModelId()}:{filename:"魔法粘贴.txt",text:textValue};
    const result=await api("/api/latex/convert",{method:"POST",body:JSON.stringify(payload)});
    $("#latexSourceOutput").value=result.latex||""; state.lastLatex=result; renderLatexDocument(result.latex);
    toast(result.requires_formula_review?"转换完成，复杂公式需要复核。":"LaTeX转换与渲染完成。");
  }catch(err){toast(err.message);}finally{done();}
}

function downloadLastLatex(){
  const source=$("#latexSourceOutput")?.value||""; if(!source){toast("请先完成转换。");return;}
  const blob=new Blob([source],{type:"application/x-tex;charset=utf-8"}), url=URL.createObjectURL(blob), a=document.createElement("a");
  a.href=url;a.download=state.lastLatex?.filename||"试卷.tex";a.click();URL.revokeObjectURL(url);
}

async function loadInstitutions() {
  const grid = $("#institutionGrid");
  if (!grid) return;
  try {
    const data = await api("/api/org/institutions");
    const list = data.institutions || [];
    grid.innerHTML = list.length
      ? list.slice(0, 8).map((inst) => `
        <article class="institution-card">
          <strong>${escapeHtml(inst.name || "教培机构")}</strong>
          <span>${escapeHtml(inst.city || "全国")} · ${Number(inst.member_count || 0)} 名机构成员 · ${Number(inst.class_count || 0)} 个班级</span>
          <p>${escapeHtml(inst.intro || "已接入 AI 错题拆博士机构管理系统，可管理学生、老师、教务与机构标识。")}</p>
          <div class="institution-card-actions">
            <a class="ghost-btn" href="/org">机构站点</a>
            <a class="primary-btn" href="/org-admin">机构管理</a>
          </div>
        </article>
      `).join("")
      : `<article class="institution-card">
          <strong>欢迎学校 / 教培机构入驻</strong>
          <span>任何人可注册机构</span>
          <p>机构可添加学生、老师、教务，成员保留普通用户能力，同时多一个机构标识。</p>
          <div class="institution-card-actions">
            <a class="primary-btn" href="/org-admin">立即注册机构</a>
            <a class="ghost-btn" href="/org">查看机构站点</a>
          </div>
        </article>`;
  } catch (err) {
    grid.innerHTML = `<div class="empty-state compact-empty"><p>${escapeHtml(err.message)}</p></div>`;
  }
}

function deliveryLabel(delivery) {
  return {
    docx: "Word",
    pptx: "PPT",
    report: "诊断报告",
    image: "PNG配图",
    map: "图谱+配图",
    diagnose: "完整闭环",
    iframe: "AiPPT 在线",
  }[delivery] || "可下载";
}

function renderPortalTools() {
  const grid = $("#portalToolGrid");
  const filters = $("#portalCategoryFilter");
  if (!grid || !filters) return;
  const categories = ["全部", ...new Set(state.portalTools.map((tool) => tool.category))];
  const current = filters.dataset.category || "全部";
  filters.innerHTML = categories.map((category) => `<button class="filter-chip ${category === current ? "active" : ""}" type="button" data-category="${escapeHtml(category)}">${escapeHtml(category)}</button>`).join("");
  filters.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      filters.dataset.category = button.dataset.category;
      renderPortalTools();
    });
  });
  const activeCategory = filters.dataset.category || "全部";
  const tools = state.portalTools
    .filter((tool) => activeCategory === "全部" || tool.category === activeCategory)
    .sort((a, b) => Number(Boolean(b.featured)) - Number(Boolean(a.featured)));
  grid.innerHTML = "";
  tools.forEach((tool) => {
    const card = document.createElement("button");
    const highlightClass = tool.featured ? "featured" : tool.id === "aippt-online3" ? "warm" : "";
    card.className = `portal-tool-card ${highlightClass}`.trim();
    card.type = "button";
    const deliveryNote = tool.featured ? "核心闭环" : tool.delivery && tool.delivery !== "diagnose" ? deliveryLabel(tool.delivery) : "";
    card.innerHTML = `
      <span class="tool-number">${escapeHtml(tool.number)}</span>
      ${tool.featured ? '<span class="tool-feature-badge">核心</span>' : ""}
      <strong>${escapeHtml(tool.label)}</strong>
      <small>${escapeHtml(tool.tagline || tool.category)}</small>
      <em>${escapeHtml(tool.category)}${deliveryNote ? ` · ${deliveryNote}` : ""}</em>
    `;
    card.addEventListener("click", () => launchTool(tool.id));
    grid.appendChild(card);
  });
}

function renderToolSelect() {
  const select = $("#toolSelect");
  if (!select) return;
  select.innerHTML = "";
  state.portalTools.forEach((tool) => {
    const option = document.createElement("option");
    option.value = tool.id;
    option.textContent = `${tool.number} · ${tool.label}`;
    select.appendChild(option);
  });
  select.value = state.activeToolId;
  updateToolRunner();
}

function activeTool() {
  return state.portalTools.find((tool) => tool.id === state.activeToolId) || state.portalTools[0];
}

function updateToolRunner() {
  const tool = activeTool();
  if (!tool) return;
  $("#toolRunnerTitle").textContent = tool.label;
  $("#toolRunnerSubtitle").textContent = tool.tagline || "输入材料后生成可直接使用的结果。";
  $("#toolRunnerBadge").textContent = tool.category || "AI工具";
  if ($("#toolSelect")) $("#toolSelect").value = tool.id;
}

function launchTool(toolId) {
  const tool = state.portalTools.find((item) => item.id === toolId);
  if (!tool) return;
  if (tool.route === "diagnose") {
    switchView("diagnose");
    return;
  }
  if (tool.route === "aippt") {
    window.location.href = "/aippt-online3.html";
    return;
  }
  if (tool.route === "report") {
    switchView("report");
    return;
  }
  if (tool.route === "card") {
    switchView("tool");
    state.activeToolId = toolId;
    updateToolRunner();
    return;
  }
  state.activeToolId = toolId;
  switchView("tool");
  updateToolRunner();
}

async function runTool() {
  const tool = activeTool();
  if (!tool) {
    toast("请先选择工具。");
    return;
  }
  const input = $("#toolInput").value.trim();
  if (!input) {
    toast("请先输入材料或上传文件。");
    return;
  }
  const button = $("#runToolBtn");
  const done = setBusy(button, "生成中...");
  try {
    const result = await api("/api/tool-runs", {
      method: "POST",
      body: JSON.stringify({
        tool_id: tool.id,
        subject: $("#toolSubjectInput").value.trim() || "自动识别",
        input_text: input,
        model_id: selectedModelId(),
      }),
    });
    $("#toolOutput").textContent = result.output_text || "";
    renderToolArtifacts(result.artifacts || []);
    renderToolReport(result.report || null);
    await loadUser();
    toast(result.artifacts?.length ? "生成完成，可下载文件。" : "生成完成。");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

function renderToolArtifacts(artifacts) {
  const root = $("#toolArtifacts");
  if (!root) return;
  if (!artifacts.length) {
    root.classList.add("hidden");
    root.innerHTML = "";
    return;
  }
  root.classList.remove("hidden");
  root.innerHTML = `
    <div class="artifact-head"><strong>可下载成品</strong><span>已生成 ${artifacts.length} 个文件</span></div>
    <div class="artifact-list">
      ${artifacts.map((item) => `
        <a class="artifact-btn" href="${escapeHtml(item.url)}" target="_blank" rel="noopener" download="${escapeHtml(item.filename)}">
          ${escapeHtml(item.label || item.kind)}
        </a>
      `).join("")}
    </div>
  `;
}

function renderToolReport(report) {
  const root = $("#toolReportPanel");
  if (!root) return;
  if (!report || !Object.keys(report).length) {
    root.classList.add("hidden");
    root.innerHTML = "";
    return;
  }
  root.classList.remove("hidden");
  const overview = report.score_overview || {};
  root.innerHTML = `
    <div class="report-grid">
      <div class="report-card"><span>报告</span><strong>${escapeHtml(report.title || "卷面学情分析")}</strong></div>
      ${overview.estimated_score ? `<div class="report-card"><span>预估得分</span><strong>${escapeHtml(overview.estimated_score)}</strong></div>` : ""}
      ${overview.pass_rate ? `<div class="report-card"><span>得分率</span><strong>${escapeHtml(overview.pass_rate)}</strong></div>` : ""}
      <div class="report-card wide"><span>结论</span><strong>${escapeHtml(report.summary || "")}</strong></div>
    </div>
  `;
}

function copyToolOutput() {
  const text = $("#toolOutput")?.textContent || "";
  navigator.clipboard?.writeText(text);
  toast("已复制生成结果。");
}



async function loadRagDocuments() {
  state.ragDocuments = await api("/api/rag/documents");
  renderRagLibrary();
}

function renderRagLibrary() {
  const summary = $("#ragLibrarySummary");
  if (!summary) return;
  const docs = state.ragDocuments || [];
  const totalChars = docs.reduce((sum, doc) => sum + Number(doc.chars || 0), 0);
  summary.innerHTML = docs.length
    ? `已入库 <strong>${docs.length}</strong> 份资料，约 <strong>${totalChars}</strong> 字。`
    : "暂无资料。可以先上传教材、讲义或直接粘贴知识点。";
}

function renderRagHits(hits) {
  const root = $("#ragHitList");
  if (!root) return;
  state.ragHits = hits || [];
  if (!state.ragHits.length) {
    root.innerHTML = `<div class="rag-empty">未检索到相关资料，智能体会按自身能力解题。</div>`;
    return;
  }
  root.innerHTML = state.ragHits.map((hit, index) => `
    <article class="rag-hit-card">
      <div><strong>${index + 1}. ${escapeHtml(hit.title || "知识片段")}</strong><span>${escapeHtml(hit.subject || "未标注")} · 相关度 ${escapeHtml(hit.score || 0)}</span></div>
      <p>${escapeHtml(hit.content || "")}</p>
    </article>
  `).join("");
}

async function saveRagDocument() {
  const files = Array.from($("#ragFileInput")?.files || []);
  const paste = $("#ragPasteInput")?.value.trim() || "";
  if (!files.length && !paste) {
    toast("请先上传资料文件，或粘贴一段资料。 ");
    return;
  }
  const button = $("#saveRagDocBtn");
  const done = setBusy(button, "入库中...");
  try {
    const subject = $("#agentSubjectInput")?.value || "自动识别";
    const title = $("#ragTitleInput")?.value.trim() || "";
    let saved = 0;
    if (paste) {
      await api("/api/rag/documents", {
        method: "POST",
        body: JSON.stringify({ title: title || "粘贴资料", filename: "paste.txt", subject, text: paste }),
      });
      saved += 1;
      $("#ragPasteInput").value = "";
    }
    for (const file of files) {
      const dataUrl = await readFileAsDataUrl(file);
      await api("/api/rag/documents", {
        method: "POST",
        body: JSON.stringify({ title, filename: file.name, subject, file_data_url: dataUrl }),
      });
      saved += 1;
    }
    if ($("#ragFileInput")) $("#ragFileInput").value = "";
    await loadRagDocuments();
    toast(`已入库 ${saved} 份资料。 `);
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

async function searchRagForCurrentQuestion() {
  const question = $("#agentQuestionInput")?.value.trim() || "";
  const answer = $("#agentStudentAnswerInput")?.value.trim() || "";
  if (!question) {
    toast("请先输入题目，再检索 RAG。 ");
    return [];
  }
  const button = $("#searchRagBtn");
  const done = button ? setBusy(button, "检索中...") : () => {};
  try {
    const hits = await api("/api/rag/search", {
      method: "POST",
      body: JSON.stringify({
        query: `${$("#agentSubjectInput")?.value || "自动识别"}\n${question}\n${answer}`,
        subject: $("#agentSubjectInput")?.value || "自动识别",
        limit: 5,
      }),
    });
    renderRagHits(hits);
    toast(hits.length ? `RAG 命中 ${hits.length} 条资料。 ` : "RAG 未命中相关资料。 ");
    return hits;
  } catch (err) {
    toast(err.message);
    return [];
  } finally {
    done();
  }
}

function renderRagStudyPanel(title, html) {
  const root = $("#ragStudyPanel");
  if (!root) return;
  root.innerHTML = `
    <div class="rag-study-head"><strong>${escapeHtml(title)}</strong></div>
    <div class="rag-study-body">${html}</div>
  `;
}

async function generateRagQuiz() {
  const topic = ($("#agentQuestionInput")?.value || $("#ragTitleInput")?.value || "错题复习").trim();
  const button = $("#generateRagQuizBtn");
  const done = button ? setBusy(button, "出卷中...") : () => {};
  try {
    const data = await api("/api/rag/generate-quiz", {
      method: "POST",
      body: JSON.stringify({
        topic,
        subject: $("#agentSubjectInput")?.value || "自动识别",
        count: 5,
      }),
    });
    const questions = data.questions || [];
    renderRagStudyPanel("RAG 自测题", questions.map((q, index) => `
      <article class="rag-study-card">
        <span class="tag muted">自测 ${index + 1}</span>
        <strong>${escapeHtml(q.question || "")}</strong>
        ${(q.options || []).length ? `<ol>${q.options.map((opt) => `<li>${escapeHtml(opt)}</li>`).join("")}</ol>` : ""}
        <details><summary>答案与解析</summary><p>${escapeHtml(q.answer || "")}</p><p>${escapeHtml(q.analysis || "")}</p></details>
      </article>
    `).join(""));
    renderRagHits(data.citations || []);
    toast("RAG 自测题已生成。");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

async function buildRagStudyOs() {
  const topic = ($("#agentQuestionInput")?.value || $("#ragTitleInput")?.value || "错题自学").trim();
  const button = $("#buildRagStudyBtn");
  const done = button ? setBusy(button, "生成中...") : () => {};
  try {
    const data = await api("/api/rag/study-os", {
      method: "POST",
      body: JSON.stringify({
        topic,
        subject: $("#agentSubjectInput")?.value || "自动识别",
      }),
    });
    const plan = data.plan || [];
    const cards = data.flashcards || [];
    const hints = data.hints || [];
    const review = data.review || [];
    renderRagStudyPanel("RAG 自学OS", `
      <div class="rag-study-section"><h4>学习路径</h4>${plan.map((item) => `<article class="rag-study-card"><strong>${escapeHtml(item.title || "")}</strong><p>${escapeHtml(item.goal || "")}</p></article>`).join("")}</div>
      <div class="rag-study-section"><h4>知识卡片</h4>${cards.map((item) => `<article class="rag-study-card"><strong>${escapeHtml(item.front || "")}</strong><p>${escapeHtml(item.back || "")}</p></article>`).join("")}</div>
      <div class="rag-study-section"><h4>分层提示</h4>${hints.map((item) => `<article class="rag-study-card"><strong>${escapeHtml(item.question || "")}</strong><p>${escapeHtml(item.try_first || "")}</p><p>${escapeHtml(item.hint || "")}</p><p>${escapeHtml(item.answer || "")}</p></article>`).join("")}</div>
      <div class="rag-study-section"><h4>错题复盘</h4>${review.map((item) => `<article class="rag-study-card warning"><strong>${escapeHtml(item.mistake || "")}</strong><p>${escapeHtml(item.fix || "")}</p></article>`).join("")}</div>
    `);
    renderRagHits(data.citations || []);
    toast("RAG 自学OS已生成。");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

function renderAgentRagCitations(result) {
  const root = $("#agentRagCitations");
  const section = $("#agentRagSection");
  if (!root || !section) return;
  const rag = result?.rag_context || {};
  const citations = rag.citations || [];
  section.classList.toggle("hidden", !rag.used && !citations.length);
  if (!rag.used && !citations.length) {
    root.innerHTML = `<div class="rag-empty">本次未使用 RAG 资料。</div>`;
    return;
  }
  root.innerHTML = `
    <div class="rag-used-summary">使用 ${escapeHtml(rag.evidence_count || citations.length)} 条资料 · ${escapeHtml(rag.how_used || "作为解题依据注入提示词")}</div>
    ${citations.map((item, index) => `
      <article class="rag-citation-card">
        <strong>${index + 1}. ${escapeHtml(item.title || "知识片段")}</strong>
        <span>${escapeHtml(item.subject || "未标注")} · 相关度 ${escapeHtml(item.score || 0)}</span>
        <p>${escapeHtml(item.excerpt || "")}</p>
      </article>
    `).join("")}
  `;
}

async function loadAgentLayers() {
  if (!state.agentLayers.length) {
    state.agentLayers = await api("/api/agent/layers");
  }
  renderAgentLayersBase();
}

function renderAgentLayersBase(resultLayers = null) {
  const rail = $("#agentLayerRail");
  const grid = $("#agentLayerGrid");
  if (!rail || !grid) return;
  const layerByKey = new Map((resultLayers || []).map((layer) => [layer.key, layer]));
  const layers = (state.agentLayers || []).map((template) => ({ ...template, ...(layerByKey.get(template.key) || {}) }));
  rail.innerHTML = layers
    .map((layer, index) => `<span class="agent-rail-node ${layer.status === "done" ? "done" : ""}"><b>${String(index + 1).padStart(2, "0")}</b>${escapeHtml(layer.name.replace(/^\d+\s*/, ""))}</span>`)
    .join("");
  grid.innerHTML = layers
    .map((layer, index) => `
      <article class="agent-layer-card ${layer.status === "done" ? "done" : ""}">
        <div class="agent-layer-index">${String(index + 1).padStart(2, "0")}</div>
        <div>
          <strong>${escapeHtml(layer.name)}</strong>
          <p>${escapeHtml(layer.summary || layer.role || "等待运行")}</p>
          <small>质检门：${escapeHtml(layer.quality_gate || "本层输出可进入下一层")}</small>
          ${layer.output ? `<em>${escapeHtml(layer.output)}</em>` : ""}
        </div>
      </article>
    `)
    .join("");
}

function renderAgentResult(run) {
  const result = run?.result || run || {};
  state.agentRun = run;
  state.agentResult = result;
  const panel = $("#agentResultPanel");
  if (!panel) return;
  panel.classList.remove("hidden");
  $("#agentResultTitle").textContent = result.title || result.question_type || "分层解题结果";
  $("#agentResultMeta").textContent = `${run?.created_at || "刚刚生成"} · ${result.subject || run?.subject || "自动识别"} · 置信度 ${Math.round(Number(result.confidence || 0.75) * 100)}%`;
  const quick = result.quick_answer || {};
  $("#agentQuickCards").innerHTML = [
    ["怎么拆解", quick.how_to_decompose],
    ["怎么更容易学", quick.make_it_easier],
    ["第一眼入口", quick.first_entry],
  ].map(([title, body]) => `<article><span>${escapeHtml(title)}</span><strong>${escapeHtml(body || "待生成")}</strong></article>`).join("");
  $("#agentFinalAnswer").textContent = result.final_answer || "未返回最终答案";
  const model = result.solution_model || {};
  $("#agentSolutionModel").textContent = `${model.model_name || "通用解题模型"}：${model.step_formula || (model.steps || []).join(" → ")}`;
  $("#agentStandardSolution").textContent = result.standard_solution || "暂无规范解析";
  $("#agentMultiSolutions").innerHTML = (result.multiple_solutions || [])
    .map((method) => `
      <article class="agent-mini-card">
        <strong>${escapeHtml(method.method_name || "方法")}</strong>
        <p>${escapeHtml(method.idea || "")}</p>
        <small>${escapeHtml((method.steps || []).join(" → "))}</small>
        ${method.pros_cons ? `<em>${escapeHtml(method.pros_cons)}</em>` : ""}
      </article>
    `)
    .join("") || `<article class="agent-mini-card"><strong>待生成</strong><p>模型未返回多解内容。</p></article>`;
  $("#agentTrainingList").innerHTML = (result.training_tasks || [])
    .map((task) => `
      <article class="agent-mini-card">
        <span>Level ${escapeHtml(task.level || "")}</span>
        <strong>${escapeHtml(task.title || "同类训练")}</strong>
        <p>${escapeHtml(task.stem || "")}</p>
        <small>答案：${escapeHtml(task.answer || "")}</small>
        ${task.analysis ? `<em>${escapeHtml(task.analysis)}</em>` : ""}
      </article>
    `)
    .join("") || `<article class="agent-mini-card"><strong>待生成</strong><p>模型未返回训练题。</p></article>`;
  const poem = result.poem || {};
  $("#agentPoemTitle").textContent = poem.title || "复盘小诗";
  $("#agentPoem").innerHTML = `
    <div class="agent-poem-lines">${(poem.lines || []).map((line) => `<p>${escapeHtml(line)}</p>`).join("") || "<p>暂无小诗。</p>"}</div>
    <div class="agent-card-list">${(poem.line_reviews || []).map((item) => `<article class="agent-mini-card"><strong>${escapeHtml(item.line || "诗句")}</strong><p>${escapeHtml(item.review || "")}</p></article>`).join("")}</div>
  `;
  renderAgentRagCitations(result);
  renderAgentLayersBase(result.layers || []);
  typesetMath(panel);
  typesetMath($("#agentLayerGrid"));
}

async function runAgentSolve() {
  const question = $("#agentQuestionInput")?.value.trim() || "";
  if (!question) {
    toast("请先输入题目内容，或上传图片/文档。 ");
    return;
  }
  const button = $("#runAgentBtn");
  const done = setBusy(button, "智能体运行中...");
  try {
    const run = await api("/api/agent/solve", {
      method: "POST",
      body: JSON.stringify({
        subject: $("#agentSubjectInput")?.value || "自动识别",
        question_text: question,
        student_answer: $("#agentStudentAnswerInput")?.value.trim() || "",
        use_rag: $("#agentUseRagToggle")?.checked !== false,
        rag_limit: 5,
        model_id: selectedModelId(),
      }),
    });
    renderAgentResult(run);
    loadHistory().catch(() => {});
    toast("分层解题完成，结果已进入历史记录。 ");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

async function openAgentRun(runId) {
  const run = await api(`/api/agent/runs/${runId}`);
  switchView("agent");
  $("#agentSubjectInput").value = run.subject || "自动识别";
  $("#agentQuestionInput").value = run.question_text || "";
  $("#agentStudentAnswerInput").value = run.student_answer || "";
  renderAgentResult(run);
}

function fillAgentSample() {
  $("#agentSubjectInput").value = "高中数学";
  $("#agentQuestionInput").value = "已知函数 f(x)=x^3-3x^2+2。\n（1）求 f(x) 的单调区间；\n（2）求 f(x) 在区间 [0,3] 上的最大值和最小值。";
  $("#agentStudentAnswerInput").value = "学生作答：先求 f'(x)=3x^2-6x，令 f'(x)=0 得 x=0,2，所以最大值是 f(0)=2，最小值是 f(2)=-2。\n批注：没有完整讨论单调区间；区间最值没有说明端点和驻点都要比较。";
  toast("样例已填入，可以直接启动分层解题。 ");
}

function copyAgentResult() {
  if (!state.agentResult) {
    toast("暂无可复制的智能体结果。 ");
    return;
  }
  navigator.clipboard?.writeText(JSON.stringify(state.agentResult, null, 2));
  toast("已复制智能体结果 JSON。 ");
}

async function loadHistory() {
  state.history = await api("/api/history");
  renderHistory();
}

function historyLabel(type) {
  return {
    all: "全部",
    diagnosis: "错题拆解",
    variant: "同类变式",
    grading: "AI批改",
    card: "学习卡片",
    agent: "解题智能体",
    tool: "通用工具",
    profile_export: "档案导出",
  }[type] || type;
}

function renderHistory() {
  const summary = $("#historySummary");
  const filter = $("#historyFilter");
  const list = $("#historyList");
  if (!summary || !filter || !list) return;
  const counts = state.history.counts || {};
  summary.innerHTML = `
    <div class="metric-card featured"><span class="label">错题拆解</span><strong>${counts.diagnosis || 0}</strong></div>
    <div class="metric-card"><span class="label">总成果</span><strong>${state.history.total || 0}</strong></div>
    <div class="metric-card"><span class="label">解题智能体</span><strong>${counts.agent || 0}</strong></div>
    <div class="metric-card"><span class="label">学习卡片</span><strong>${counts.card || 0}</strong></div>
    <div class="metric-card"><span class="label">工具生成</span><strong>${counts.tool || 0}</strong></div>
  `;
  const types = ["all", "diagnosis", "agent", "variant", "grading", "card", "tool", "profile_export"];
  filter.innerHTML = types.map((type) => `<button class="filter-chip ${state.historyFilter === type ? "active" : ""}" type="button" data-type="${type}">${historyLabel(type)}</button>`).join("");
  filter.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.historyFilter = button.dataset.type;
      renderHistory();
    });
  });
  const items = (state.history.items || []).filter((item) => state.historyFilter === "all" || item.type === state.historyFilter);
  if (!items.length) {
    const hint = state.user
      ? "生成拆题、工具结果、卡片或档案后，会自动出现在这里。"
      : "请先登录，您的生成记录将与其它账号隔离保存。";
    list.innerHTML = `<article class="archive-empty"><h3>暂无历史</h3><p>${hint}</p></article>`;
    return;
  }
  list.innerHTML = "";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "history-card";
    const thumb = item.image_url ? `<img src="${escapeHtml(item.image_url)}" alt="学习卡片" />` : `<span>${escapeHtml(item.label.slice(0, 2))}</span>`;
    card.innerHTML = `
      <div class="history-thumb">${thumb}</div>
      <div>
        <div class="history-card-head"><span class="tag muted">${escapeHtml(item.label)}</span><small>${escapeHtml(item.created_at || "")}</small></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.summary || "")}</p>
        <div class="archive-meta"><span>${escapeHtml(item.subject || "未识别学科")}</span></div>
      </div>
      <div class="history-actions"></div>
    `;
    const actions = card.querySelector(".history-actions");
    const openBtn = document.createElement("button");
    openBtn.className = "ghost-btn";
    openBtn.type = "button";
    openBtn.textContent = item.type === "profile_export" ? "下载" : "打开";
    openBtn.addEventListener("click", () => openHistoryItem(item));
    actions.appendChild(openBtn);
    list.appendChild(card);
  });
}

async function openHistoryItem(item) {
  if (item.type === "card" && item.image_url) {
    window.open(item.image_url, "_blank");
    return;
  }
  if (item.type === "profile_export" && item.export_id) {
    const result = await api(`/api/profile/exports/${item.export_id}`);
    const blob = new Blob([result.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = result.filename || "个人学习档案.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return;
  }
  if (item.type === "agent" && item.agent_run_id) {
    await openAgentRun(item.agent_run_id);
    toast("已打开智能体历史记录。 ");
    return;
  }
  if (item.type === "tool" && item.tool_run_id) {
    const result = await api(`/api/tool-runs/${item.tool_run_id}`);
    state.activeToolId = result.tool_id;
    switchView("tool");
    $("#toolSubjectInput").value = result.subject || "自动识别";
    $("#toolInput").value = result.input_text || "";
    $("#toolOutput").textContent = result.output_text || "";
    renderToolArtifacts(result.artifacts || []);
    renderToolReport(result.report || null);
    updateToolRunner();
    return;
  }
  if (item.wrong_question_id) {
    const detail = await api(`/api/wrong-questions/${item.wrong_question_id}`);
    switchView("diagnose");
    renderDiagnosis(detail);
    toast("已打开对应题目。");
  }
}

function historyLabelClean(type) {
  return {
    all: "全部",
    diagnosis: "错题拆解",
    variant: "同类变式",
    grading: "AI批改",
    card: "学习卡片",
    agent: "解题智能体",
    tool: "通用工具",
    profile_export: "档案导出",
  }[type] || type;
}

historyLabel = historyLabelClean;
renderHistory = function renderHistoryClean() {
  const summary = $("#historySummary");
  const filter = $("#historyFilter");
  const list = $("#historyList");
  if (!summary || !filter || !list) return;
  const counts = state.history.counts || {};
  summary.innerHTML = `
    <div class="metric-card featured"><span class="label">错题拆解</span><strong>${counts.diagnosis || 0}</strong></div>
    <div class="metric-card"><span class="label">总成果</span><strong>${state.history.total || 0}</strong></div>
    <div class="metric-card"><span class="label">解题智能体</span><strong>${counts.agent || 0}</strong></div>
    <div class="metric-card"><span class="label">学习卡片</span><strong>${counts.card || 0}</strong></div>
    <div class="metric-card"><span class="label">工具生成</span><strong>${counts.tool || 0}</strong></div>
  `;
  const types = ["all", "diagnosis", "agent", "variant", "grading", "card", "tool", "profile_export"];
  filter.innerHTML = types.map((type) => `<button class="filter-chip ${state.historyFilter === type ? "active" : ""}" type="button" data-type="${type}">${historyLabel(type)}</button>`).join("");
  filter.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.historyFilter = button.dataset.type;
      renderHistory();
    });
  });
  const items = (state.history.items || []).filter((item) => state.historyFilter === "all" || item.type === state.historyFilter);
  if (!items.length) {
    const hint = state.user
      ? "生成拆题、工具结果、卡片或档案后，会自动出现在这里。"
      : "请先登录，您的生成记录将与其它账号隔离保存。";
    list.innerHTML = `<article class="archive-empty"><h3>暂无历史</h3><p>${hint}</p></article>`;
    return;
  }
  list.innerHTML = "";
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "history-card";
    const thumb = item.image_url ? `<img src="${escapeHtml(item.image_url)}" alt="学习卡片" />` : `<span>${escapeHtml(item.label.slice(0, 2))}</span>`;
    card.innerHTML = `
      <div class="history-thumb">${thumb}</div>
      <div>
        <div class="history-card-head"><span class="tag muted">${escapeHtml(item.label)}</span><small>${escapeHtml(item.created_at || "")}</small></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.summary || "")}</p>
        <div class="archive-meta"><span>${escapeHtml(item.subject || "未识别学科")}</span></div>
      </div>
      <div class="history-actions"></div>
    `;
    const actions = card.querySelector(".history-actions");
    const openBtn = document.createElement("button");
    openBtn.className = "ghost-btn";
    openBtn.type = "button";
    openBtn.textContent = item.type === "profile_export" ? "下载" : "打开";
    openBtn.addEventListener("click", () => openHistoryItem(item));
    actions.appendChild(openBtn);
    list.appendChild(card);
  });
};

openHistoryItem = async function openHistoryItemClean(item) {
  if (item.type === "card" && item.image_url) {
    window.open(item.image_url, "_blank");
    return;
  }
  if (item.type === "profile_export" && item.export_id) {
    const result = await api(`/api/profile/exports/${item.export_id}`);
    const blob = new Blob([result.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = result.filename || "个人学习档案.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return;
  }
  if (item.type === "agent" && item.agent_run_id) {
    await openAgentRun(item.agent_run_id);
    toast("已打开智能体历史记录。");
    return;
  }
  if (item.type === "tool" && item.tool_run_id) {
    const result = await api(`/api/tool-runs/${item.tool_run_id}`);
    state.activeToolId = result.tool_id;
    switchView("tool");
    $("#toolSubjectInput").value = result.subject || "自动识别";
    $("#toolInput").value = result.input_text || "";
    $("#toolOutput").textContent = result.output_text || "";
    renderToolArtifacts(result.artifacts || []);
    renderToolReport(result.report || null);
    updateToolRunner();
    return;
  }
  if (item.wrong_question_id) {
    const detail = await api(`/api/wrong-questions/${item.wrong_question_id}`);
    switchView("diagnose");
    renderDiagnosis(detail);
    toast("已打开对应题目。");
  }
};

async function loadModels() {
  state.models = await api("/api/models");
  const select = $("#modelSelect");
  select.innerHTML = "";
  state.models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = `${model.name} · ${model.model}${model.is_default ? "（默认）" : ""}`;
    select.appendChild(option);
  });
  const defaultModel = state.models.find((m) => m.is_default) || state.models[0];
  state.selectedModelId = defaultModel?.id || "";
  select.value = state.selectedModelId;
}

async function loadImageModels(admin = false) {
  state.imageModels = await api(admin ? "/api/admin/image-models" : "/api/image-models");
  renderImageModelSelect();
}

function renderImageModelSelect() {
  const select = $("#imageModelSelect");
  if (!select) return;
  select.innerHTML = "";
  state.imageModels.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = `${model.name} · ${model.model}${model.is_default ? "（默认）" : ""}`;
    select.appendChild(option);
  });
  const defaultModel = state.imageModels.find((m) => m.is_default) || state.imageModels[0];
  state.selectedImageModelId = defaultModel?.id || "";
  select.value = state.selectedImageModelId;
}

function selectedModelId() {
  return $("#modelSelect").value || state.selectedModelId;
}

function selectedImageModelId() {
  return $("#imageModelSelect")?.value || state.selectedImageModelId;
}

function renderDiagnosis(item) {
  state.currentWrong = item;
  state.variants = item.variants || [];
  const diagnosis = item.diagnosis || {};
  const standardAnswer = diagnosis.standard_answer || {};

  $("#emptyState").classList.add("hidden");
  $("#diagnosisResult").classList.remove("hidden");
  $("#resultStatus").textContent = statusText(item.status);
  $("#resultStatus").className = item.status === "review_needed" ? "tag warn" : item.status === "passed" ? "tag success" : "tag success";

  $("#guestSaveBanner")?.classList.toggle("hidden", Boolean(state.user));

  $("#corePattern").textContent = diagnosis.core_pattern || "待归纳题型";
  const workflowMeta = item.mastery_score > 0
    ? ` · 掌握度 ${item.mastery_score}%${item.next_review_at ? ` · 下次复习 ${String(item.next_review_at).slice(0, 10)}` : ""}`
    : "";
  $("#confidenceText").textContent = `置信度 ${Math.round((item.confidence || diagnosis.confidence || 0.75) * 100)}% · ${diagnosis.topic || diagnosis.subject || "自动识别"}${workflowMeta}`;
  $("#finalAnswer").textContent = standardAnswer.final_answer || "模型未返回最终答案，请查看下方拆解步骤。";
  $("#conciseSolution").textContent = standardAnswer.concise_solution || "暂无简洁解析。";

  renderChips($("#kpList"), diagnosis.knowledge_points || []);
  $("#problemGoal").textContent = diagnosis.problem_goal || "模型未返回题目目标";
  $("#totalFormula").textContent = diagnosis.decomposition?.total_formula || "未返回总拆解公式";

  const answerAnalysis = diagnosis.student_answer_analysis || {};
  $("#answerStatus").textContent = answerAnalysis.answer_status || (item.student_wrong_answer ? "已记录作答，等待模型细分" : "未提供作答");
  $("#answerIssue").textContent = answerAnalysis.likely_issue || (item.student_wrong_answer ? "已保存学生作答/卡点，可对照下面的拆题步骤定位断点。" : "可以粘贴学生答案、手写过程或批改痕迹，让系统一起判断。");
  $("#answerPresence").textContent = answerAnalysis.answer_presence || (item.student_wrong_answer ? "已提供" : "未提供");
  $("#answerNextAction").textContent = answerAnalysis.next_action || (item.student_wrong_answer ? "对照模型步骤复盘" : "补充作答过程");
  $("#answerEvidence").innerHTML = (answerAnalysis.evidence || []).map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("");
  $("#answerExtractedWork").textContent = answerAnalysis.extracted_work || item.student_wrong_answer || "";

  const strategy = diagnosis.learning_strategy || {};
  $("#decompositionAnswer").textContent = strategy.decomposition_answer || "先识别题型入口，再拆条件、选模型、执行步骤并验算。";
  $("#makeEasier").textContent = strategy.make_it_easier || "先做更小的原型题，把难点拆成 1-2 个微练习，再迁移回原题。";
  $("#entryPoint").textContent = strategy.entry_point || diagnosis.core_pattern || "题型入口";
  $("#teacherHint").textContent = strategy.teacher_hint || "这道题第一眼最像哪一类已经做过的题？";
  renderChips($("#cognitiveLadder"), strategy.cognitive_ladder || []);
  renderChips($("#microDrills"), strategy.micro_drills || []);

  $("#stepFormulaList").innerHTML = (diagnosis.decomposition?.step_formulas || [])
    .map((step) => stackCard(step.name, `${step.formula}\n${step.operation}`, step.student_trap ? `易错点：${step.student_trap}` : ""))
    .join("");

  $("#analogyTheme").textContent = diagnosis.fun_analogy?.theme || "趣味比喻";
  $("#analogyOverview").textContent = diagnosis.fun_analogy?.overview || "";
  $("#analogySteps").innerHTML = (diagnosis.fun_analogy?.steps || [])
    .map((step) => stackCard(step.step, step.analogy, step.math_action))
    .join("");

  $("#modelList").innerHTML = (diagnosis.solution_models || [])
    .map((model) =>
      stackCard(
        model.model_name,
        `适用：${model.applies_when || ""}\n步骤：${(model.steps || []).join(" → ")}`,
        `检查点：${(model.checkpoints || []).join("；")} 常见错误：${(model.common_mistakes || []).join("；")}`
      )
    )
    .join("");

  $("#solutionList").innerHTML = (diagnosis.multiple_solutions || [])
    .map((method) =>
      stackCard(
        method.method_name,
        `${method.idea || ""}\n${(method.steps || []).join(" → ")}`,
        method.pros_cons || ""
      )
    )
    .join("");

  const reserved = diagnosis.mother_question_reserved || {};
  $("#reservedMother").innerHTML = `
    <strong>${escapeHtml(reserved.name || "母题雏形待沉淀")}</strong>
    <p>${escapeHtml(reserved.abstract_pattern || "后续接入正式母题库后沉淀。")}</p>
    <div class="chip-row">${(reserved.recognition_signals || []).map((s) => `<span class="chip">${escapeHtml(s)}</span>`).join("")}</div>
    <small>${escapeHtml(reserved.future_interface_hint || "接口已预留。")}</small>
  `;

  $("#poemTitle").textContent = diagnosis.poem?.title || "复盘小诗";
  $("#poemLines").innerHTML = (diagnosis.poem?.lines || []).map((line) => `<p>${escapeHtml(line)}</p>`).join("");
  $("#poemReviews").innerHTML = (diagnosis.poem?.line_reviews || [])
    .map((item) => stackCard(item.line, item.review))
    .join("");

  renderStudyCards(item.study_cards || []);

  updateDiagnoseProgress("diagnose");
  if (state.variants.length) {
    renderVariants(state.variants);
    updateDiagnoseProgress("training");
    requestAnimationFrame(() => {
      $("#trainingPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  } else {
    $("#trainingPanel")?.classList.add("hidden");
  }
  typesetMath($("#diagnosisResult"));
  typesetMath($("#trainingPanel"));
}

function renderStudyCards(cards) {
  const root = $("#studyCardGallery");
  if (!root) return;
  root.innerHTML = "";
  if (!cards.length) {
    root.innerHTML = `
      <div class="study-card-empty">
        <strong>还没有生成卡片</strong>
        <span>点上方按钮，把这道题整理成可保存、可打印的学习训练卡。</span>
      </div>
    `;
    return;
  }
  cards.forEach((card) => {
    const item = document.createElement("article");
    item.className = "study-card-preview";
    item.innerHTML = `
      <a class="study-card-image" href="${escapeHtml(card.image_url)}" target="_blank" rel="noreferrer">
        <img src="${escapeHtml(card.image_url)}" alt="错题学习卡片" />
      </a>
      <div class="study-card-meta">
        <div>
          <strong>${escapeHtml(card.model || "GPT Image")}</strong>
          <span>${escapeHtml(card.created_at || "")} · ${escapeHtml(card.size || "")}</span>
        </div>
        <div class="study-card-actions">
          <a class="ghost-btn" href="${escapeHtml(card.image_url)}" target="_blank" rel="noreferrer">查看大图</a>
          <a class="ghost-btn" href="${escapeHtml(card.image_url)}" download>下载</a>
        </div>
      </div>
    `;
    root.appendChild(item);
  });
}

async function generateStudyCard() {
  if (!state.currentWrong) {
    toast("请先完成一道题的 AI 拆解。");
    return;
  }
  if (!state.imageModels.length) {
    toast("请先在后台配置图片生成模型。");
    return;
  }
  const button = $("#generateStudyCardBtn");
  const done = setBusy(button, "卡片生成中...");
  try {
    const card = await api(`/api/wrong-questions/${state.currentWrong.id}/cards`, {
      method: "POST",
      body: JSON.stringify({
        image_model_id: selectedImageModelId(),
        style: $("#cardStyleInput")?.value.trim() || "",
      }),
    });
    state.currentWrong.study_cards = [card, ...(state.currentWrong.study_cards || [])];
    renderStudyCards(state.currentWrong.study_cards);
    toast("学习卡片已生成。");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

function renderVariants(variants) {
  $("#trainingPanel").classList.remove("hidden");
  $("#variantList").innerHTML = "";
  let correctCount = 0;
  variants.forEach((variant) => {
    const latest = (variant.answers || [])[0];
    if (latest?.is_correct) correctCount += 1;
    const card = document.createElement("article");
    card.className = "variant-card";
    card.innerHTML = `
      <div>
        <span class="tag">${["同型巩固", "轻微变式", "综合迁移"][variant.level - 1] || `第 ${variant.level} 题`}</span>
        <h3>${escapeHtml(variant.title || "巩固题")}</h3>
      </div>
      <p class="variant-stem">${escapeHtml(variant.stem)}</p>
      <label class="field">
        <span>你的答案</span>
        <textarea rows="4" placeholder="写出关键步骤和结论"></textarea>
      </label>
      <button class="ghost-btn submit-answer" type="button">提交 AI 批改</button>
      <div class="grade-box hidden"></div>
    `;
    const textarea = card.querySelector("textarea");
    const button = card.querySelector(".submit-answer");
    const gradeBox = card.querySelector(".grade-box");
    button.addEventListener("click", async () => {
      if (!textarea.value.trim()) {
        toast("先写下你的答案或关键步骤。");
        return;
      }
      const done = setBusy(button, "批改中...");
      try {
        const result = await api(`/api/exercise-variants/${variant.id}/answers`, {
          method: "POST",
          body: JSON.stringify({ answer_text: textarea.value.trim(), model_id: selectedModelId() }),
        });
        gradeBox.className = `grade-box ${result.is_correct ? "pass" : "fail"}`;
        gradeBox.innerHTML = `
          <strong>${result.is_correct ? "通过" : "待巩固"} · ${result.score}分</strong>
          <div>${escapeHtml(result.comment)}</div>
          <div>参考答案：${escapeHtml(result.reference_answer)}</div>
          <div>${escapeHtml(result.analysis)}</div>
          <div>${escapeHtml(result.poem_review || "")}</div>
        `;
        gradeBox.classList.remove("hidden");
        await refreshCurrentWrong();
      } catch (err) {
        toast(err.message);
      } finally {
        done();
      }
    });
    $("#variantList").appendChild(card);
    typesetMath(card);
  });
  const passBadge = $("#passBadge");
  if (passBadge) {
    if (state.currentWrong?.status === "passed") {
      passBadge.textContent = "已过关";
      passBadge.className = "tag success";
    } else {
      passBadge.textContent = `训练中 · ${correctCount}/${variants.length} 正确 · ${PASS_REQUIRED_CORRECT}/${variants.length || 3} 即过关`;
      passBadge.className = "tag muted";
    }
  }
}

async function refreshCurrentWrong() {
  if (!state.currentWrong) return;
  const item = await api(`/api/wrong-questions/${state.currentWrong.id}`);
  state.currentWrong = item;
  state.variants = item.variants || [];
  if (state.variants.length) renderVariants(state.variants);
  if (item.status === "passed") {
    updateDiagnoseProgress("archive");
    toast("恭喜，已过关！这道题可继续在错题本中回看。");
  }
}

async function runOcr() {
  if (!state.imageDataUrl) {
    toast("请先选择图片。");
    return;
  }
  const done = setBusy($("#ocrBtn"), "OCR识别中...");
  try {
    const result = await api("/api/ocr", {
      method: "POST",
      body: JSON.stringify({ image_data_url: state.imageDataUrl, model_id: selectedModelId() }),
    });
    state.ocrText = result.ocr_text || "";
    state.ocrConfidence = Number(result.confidence ?? result.ocr_confidence ?? 0.85);
    $("#questionText").value = result.printed_question || result.ocr_text || "";
    const extra = [result.student_work, result.teacher_marks].filter(Boolean).join("\n");
    if (extra && !$("#wrongAnswer").value.trim()) $("#wrongAnswer").value = extra;
    setCalibrationBanner(questionNeedsCalibration($("#questionText").value, state.ocrConfidence));
    updateDiagnoseProgress("input");
    toast(extra ? "OCR完成，已识别题目和作答/批注。" : "OCR完成，请检查题干。");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

async function diagnose() {
  const text = $("#questionText").value.trim();
  if (!text) {
    toast("请先完成 OCR 或输入题干。");
    return;
  }
  if (questionNeedsCalibration(text, state.ocrConfidence)) {
    setCalibrationBanner(true);
    $("#questionText").focus();
    toast("题干可能需要校准，请先修正后再拆解。");
    return;
  }
  setCalibrationBanner(false);
  const done = setBusy($("#diagnoseBtn"), "拆解中...");
  try {
    const item = await api("/api/diagnose", {
      method: "POST",
      body: JSON.stringify({
        subject: $("#subjectSelect").value,
        input_mode: state.inputMode,
        image_data_url: state.imageDataUrl,
        ocr_text: state.ocrText,
        question_text: text,
        student_wrong_answer: $("#wrongAnswer").value.trim(),
        model_id: selectedModelId(),
      }),
    });
    if (!state.user) rememberGuestWrong(item.id);
    renderDiagnosis(item);
    renderTodayPanel().catch(() => {});
    toast((item.variants || []).length ? "错题拆解完成，请先做第 1 道巩固题。" : "错题拆解完成。");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

async function loadLibrary() {
  const list = await fetchWrongQuestions();
  const root = $("#libraryList");
  root.innerHTML = "";
  if (!list.length) {
    root.innerHTML = `<div class="empty-state"><h3>还没有错题</h3><p>点击「开始错题拆解」上传第一道错题，拆解与巩固进度会自动沉淀到这里。${state.user ? "" : "未登录时也会暂存到本机。"}</p><button class="primary-btn" type="button" id="libraryEmptyStartBtn">开始错题拆解</button></div>`;
    $("#libraryEmptyStartBtn")?.addEventListener("click", () => switchView("diagnose"));
    return;
  }
  list.forEach((item) => {
    const diagnosis = item.diagnosis || {};
    const progress = variantProgress(item);
    const card = document.createElement("article");
    card.className = "library-card";
    const actionLabel = item.status === "passed" ? "查看解析" : progress.done > 0 ? "继续训练" : "开始训练";
    card.innerHTML = `
      <div class="library-card-main">
        <div class="library-card-meta">
          <span class="tag ${item.status === "passed" ? "success" : item.status === "review_needed" ? "warn" : "muted"}">${statusText(item.status)}</span>
          <span class="library-meta-text">${escapeHtml(subjectOf(item))} · ${escapeHtml(formatDate(item.created_at))}</span>
          ${progress.total ? `<span class="library-meta-text">巩固 ${progress.done}/${progress.total}</span>` : ""}
        </div>
        <h3>${escapeHtml(diagnosis.core_pattern || "题目拆解")}</h3>
        <p class="library-snippet">${escapeHtml(item.corrected_text)}</p>
      </div>
      <div class="library-card-actions">
        <button class="primary-btn library-action" type="button">${actionLabel}</button>
        <button class="ghost-btn library-view" type="button">查看</button>
      </div>
    `;
    const openItem = async () => {
      switchView("diagnose");
      const detail = await api(`/api/wrong-questions/${item.id}`);
      renderDiagnosis(detail);
      toast("已打开错题记录。");
    };
    card.querySelector(".library-action").addEventListener("click", openItem);
    card.querySelector(".library-view").addEventListener("click", openItem);
    root.appendChild(card);
  });
  typesetMath(root);
}

function statusText(status) {
  return {
    diagnosed: "已拆解",
    review_needed: "需复核",
    training: "训练中",
    remediation: "回炉巩固",
    review_scheduled: "待间隔复习",
    mastered: "已掌握",
    passed: "已过关",
  }[status] || status;
}

function subjectOf(item) {
  const subject = String(item?.subject || item?.diagnosis?.subject || "").trim();
  return subject && !/^\?+$/.test(subject) ? subject : "未识别学科";
}


function shareUrl(token) {
  return `${window.location.origin}/share.html?token=${encodeURIComponent(token)}`;
}

async function loadProfileShares() {
  state.profileShares = await api("/api/profile/shares");
  renderShareList();
}

function renderShareList() {
  const root = $("#shareList");
  if (!root) return;
  const shares = state.profileShares || [];
  if (!state.user) {
    root.innerHTML = `<article class="share-empty"><strong>登录后可生成共享链接</strong><p>共享链接需要绑定账号，便于随时关闭和追踪查看时间。</p></article>`;
    return;
  }
  if (!shares.length) {
    root.innerHTML = `<article class="share-empty"><strong>暂无共享链接</strong><p>点击“生成共享链接”，即可把学习状态发给家教或家长。</p></article>`;
    return;
  }
  root.innerHTML = "";
  shares.forEach((share) => {
    const url = shareUrl(share.token);
    const card = document.createElement("article");
    card.className = `share-card ${share.status !== "active" ? "revoked" : ""}`;
    card.innerHTML = `
      <div class="share-card-main">
        <span class="tag ${share.status === "active" ? "success" : "muted"}">${share.status === "active" ? "共享中" : "已关闭"}</span>
        <strong>${escapeHtml(share.title || "学习状态共享")}</strong>
        <p>${escapeHtml(share.audience || "家教/家长/教务")} · 创建于 ${escapeHtml(formatDate(share.created_at))}${share.last_viewed_at ? ` · 最近查看 ${escapeHtml(formatDate(share.last_viewed_at))}` : ""}</p>
        ${share.note ? `<small>${escapeHtml(share.note)}</small>` : ""}
        <input class="text-input share-url-input" readonly value="${escapeHtml(url)}" />
      </div>
      <div class="share-card-actions">
        <button class="ghost-btn copy-share" type="button">复制链接</button>
        <a class="ghost-btn" href="${escapeHtml(url)}" target="_blank" rel="noopener">预览</a>
        ${share.status === "active" ? `<button class="ghost-btn revoke-share" type="button">关闭</button>` : ""}
      </div>
    `;
    card.querySelector(".copy-share")?.addEventListener("click", async () => {
      await navigator.clipboard?.writeText(url);
      toast("共享链接已复制。 ");
    });
    card.querySelector(".revoke-share")?.addEventListener("click", async () => {
      await api(`/api/profile/shares/${share.id}/revoke`, { method: "POST", body: "{}" });
      await loadProfileShares();
      toast("共享链接已关闭。 ");
    });
    root.appendChild(card);
  });
}

async function createProfileShare() {
  if (!state.user) {
    openModal("authModal");
    toast("请先登录后再生成共享链接。 ");
    return;
  }
  const button = $("#createShareBtn");
  const done = setBusy(button, "生成中...");
  try {
    const share = await api("/api/profile/share", {
      method: "POST",
      body: JSON.stringify({
        title: $("#shareTitleInput")?.value.trim() || "学习状态共享",
        audience: $("#shareAudienceInput")?.value.trim() || "家教/家长/教务",
        note: $("#shareNoteInput")?.value.trim() || "",
        permissions: { report: true, profile: true, history: true, questions: true },
      }),
    });
    await loadProfileShares();
    await navigator.clipboard?.writeText(shareUrl(share.token));
    toast("共享链接已生成并复制。 ");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

async function loadProfile() {
  state.profile = await api("/api/profile");
  loadProfileShares().catch((err) => toast(err.message));
  const subjectSelect = $("#archiveSubjectSelect");
  const current = subjectSelect.value || "全部学科";
  subjectSelect.innerHTML = `<option value="全部学科">全部学科</option>`;
  (state.profile.subjects || []).forEach((subject) => {
    const option = document.createElement("option");
    option.value = subject.name;
    option.textContent = `${subject.name}（${subject.count}）`;
    subjectSelect.appendChild(option);
  });
  subjectSelect.value = [...subjectSelect.options].some((option) => option.value === current) ? current : "全部学科";
  renderArchiveList();
}

function archiveVisibleItems() {
  const subject = $("#archiveSubjectSelect").value || "全部学科";
  return (state.profile.items || []).filter((item) => subject === "全部学科" || subjectOf(item) === subject);
}

function renderArchiveList() {
  const root = $("#archiveList");
  const subject = $("#archiveSubjectSelect").value || "全部学科";
  const items = archiveVisibleItems();
  $("#archiveCount").textContent = items.length;
  root.innerHTML = "";
  if (!items.length) {
    root.innerHTML = `<article class="archive-empty"><h3>暂无可导出的题目</h3><p>完成 OCR 拆题后，每道题会按学科进入个人档案。</p></article>`;
    return;
  }
  const visibleItems = subject === "全部学科"
    ? [...items].sort((a, b) => subjectOf(a).localeCompare(subjectOf(b), "zh-Hans-CN") || String(b.created_at || "").localeCompare(String(a.created_at || "")))
    : items;
  let currentSubject = "";
  visibleItems.forEach((item) => {
    const diagnosis = item.diagnosis || {};
    const itemSubject = subjectOf(item);
    if (subject === "全部学科" && itemSubject !== currentSubject) {
      currentSubject = itemSubject;
      const divider = document.createElement("div");
      divider.className = "archive-subject-divider";
      divider.innerHTML = `<span>${escapeHtml(itemSubject)}</span><small>独立学习档案</small>`;
      root.appendChild(divider);
    }
    const card = document.createElement("article");
    card.className = "archive-card";
    card.dataset.id = item.id;
    card.innerHTML = `
      <div class="archive-card-head">
        <label class="archive-select">
          <input type="checkbox" class="archive-question" checked />
          <span>${escapeHtml(itemSubject)}</span>
        </label>
        <span class="tag muted">${escapeHtml(statusText(item.status || "已记录"))}</span>
      </div>
      <h3>${escapeHtml(diagnosis.core_pattern || "题目档案")}</h3>
      <p>${escapeHtml(item.corrected_text || "")}</p>
      <div class="archive-meta">
        <span>${escapeHtml(item.created_at || "未记录时间")}</span>
        <span>${(item.variants || []).length} 道同类题</span>
      </div>
      <div class="archive-field-grid">
        ${archiveField("question", "题目", true)}
        ${archiveField("student", "作答情况", true)}
        ${archiveField("answer", "答案", true)}
        ${archiveField("analysis", "解析", true)}
        ${archiveField("strategy", "学习方法", true)}
        ${archiveField("thinking", "详细思路", true)}
        ${archiveField("multi", "一题多解", true)}
        ${archiveField("poem", "小诗复盘", true)}
        ${archiveField("similar", "同类题", true)}
        ${archiveField("ocr", "OCR原文", false)}
      </div>
    `;
    root.appendChild(card);
  });
}

function archiveField(value, label, checked) {
  return `<label><input type="checkbox" class="archive-field" value="${value}" ${checked ? "checked" : ""} /> ${label}</label>`;
}

function applyBulkFields() {
  const selected = new Set($$(".bulk-field").filter((item) => item.checked).map((item) => item.value));
  $$(".archive-card").forEach((card) => {
    card.querySelectorAll(".archive-field").forEach((checkbox) => {
      checkbox.checked = selected.has(checkbox.value);
    });
  });
  toast("已应用到所有题目。");
}

async function exportProfile() {
  const selections = {};
  $$(".archive-card").forEach((card) => {
    const chosen = card.querySelector(".archive-question")?.checked;
    if (!chosen) return;
    const options = {};
    card.querySelectorAll(".archive-field").forEach((checkbox) => {
      options[checkbox.value] = checkbox.checked;
    });
    selections[card.dataset.id] = options;
  });
  if (!Object.keys(selections).length) {
    toast("请至少选择一道题目。");
    return;
  }
  const done = setBusy($("#exportProfileBtn"), "生成档案中...");
  try {
    const result = await api("/api/profile/export", {
      method: "POST",
      body: JSON.stringify({
        subject: $("#archiveSubjectSelect").value || "全部学科",
        selections,
      }),
    });
    const blob = new Blob([result.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = result.filename || "个人学习档案.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    toast(`已导出 ${result.count} 道题。`);
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

async function loadReport() {
  if (!state.user) {
    const list = await fetchWrongQuestions();
    const passed = list.filter((item) => item.status === "passed").length;
    const report = {
      total_wrong_questions: list.length,
      passed_questions: passed,
      pass_rate: list.length ? Math.round((passed / list.length) * 1000) / 10 : 0,
      weak_mothers: aggregateFieldCounts(list, (item) => item.diagnosis?.core_pattern || "未归类", "name"),
      error_causes: aggregateFieldCounts(
        list,
        (item) => (item.diagnosis?.student_answer_analysis || {}).answer_status || "",
        "label",
        new Set(["", "未提供作答", "待模型进一步判断"]),
      ),
    };
    renderReport(report);
    return;
  }
  const report = await api("/api/report");
  renderReport(report);
}

function aggregateFieldCounts(list, getter, field, skip = new Set()) {
  const counts = {};
  list.forEach((item) => {
    const value = String(getter(item) || "").trim();
    if (!value || skip.has(value)) return;
    counts[value] = (counts[value] || 0) + 1;
  });
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([value, count]) => ({ [field]: value, count }));
}

function renderReport(report) {
  $("#reportCards").innerHTML = `
    <div class="metric-card featured"><span class="label">题目总数</span><strong>${report.total_wrong_questions}</strong></div>
    <div class="metric-card"><span class="label">已过关</span><strong>${report.passed_questions}</strong></div>
    <div class="metric-card"><span class="label">过关率</span><strong>${report.pass_rate}%</strong></div>
  `;
  renderRank($("#weakMothers"), report.weak_mothers, "name");
  renderRank($("#errorCauses"), report.error_causes, "label");
}

async function renderTodayPanel() {
  const summary = $("#todaySummary");
  const listRoot = $("#todayList");
  if (!summary || !listRoot) return;
  const list = await fetchWrongQuestions();
  const now = Date.now();
  const dueReview = list.filter((item) => item.workflow_state === "review_scheduled" && item.next_review_at && Date.parse(item.next_review_at) <= now);
  const pendingTraining = list.filter((item) => ["diagnosed", "training", "remediation"].includes(item.status));
  const reviewNeeded = list.filter((item) => item.status === "review_needed");
  const passedRecent = list.filter((item) => item.status === "passed").slice(0, 3);
  summary.innerHTML = `
    <div class="today-card"><span>待训练</span><strong>${pendingTraining.length}</strong></div>
    <div class="today-card warn"><span>需复核</span><strong>${reviewNeeded.length}</strong></div>
    <div class="today-card success"><span>今日复习</span><strong>${dueReview.length}</strong></div>
  `;
  const focus = [...reviewNeeded, ...dueReview, ...pendingTraining].slice(0, 5);
  listRoot.innerHTML = "";
  if (!focus.length) {
    listRoot.innerHTML = `<div class="empty-state compact-empty"><p>暂无待办错题。上传一道错题开始今日训练。</p><button class="primary-btn" type="button" id="todayStartBtn">开始错题拆解</button></div>`;
    $("#todayStartBtn")?.addEventListener("click", () => switchView("diagnose"));
    return;
  }
  focus.forEach((item) => {
    const diagnosis = item.diagnosis || {};
    const progress = variantProgress(item);
    const row = document.createElement("article");
    row.className = "today-item";
    row.innerHTML = `
      <div>
        <span class="tag ${item.status === "review_needed" ? "warn" : "muted"}">${statusText(item.status)}</span>
        <strong>${escapeHtml(diagnosis.core_pattern || "待训练错题")}</strong>
        <small>${escapeHtml(subjectOf(item))}${progress.total ? ` · 巩固 ${progress.done}/${progress.total}` : ""}</small>
      </div>
      <button class="ghost-btn" type="button">继续</button>
    `;
    row.querySelector("button").addEventListener("click", async () => {
      switchView("diagnose");
      renderDiagnosis(await api(`/api/wrong-questions/${item.id}`));
    });
    listRoot.appendChild(row);
  });
}

function renderRank(root, rows, field) {
  root.innerHTML = "";
  if (!rows.length) {
    root.innerHTML = `<div class="rank-card"><span>暂无数据</span><strong>0</strong></div>`;
    return;
  }
  rows.forEach((row) => {
    const card = document.createElement("div");
    card.className = "rank-card";
    card.innerHTML = `<span>${escapeHtml(row[field])}</span><strong>${row.count}</strong>`;
    root.appendChild(card);
  });
}

async function loadMothers() {
  const mothers = await api("/api/mother-questions");
  $("#motherList").innerHTML = "";
  if (!mothers.length) {
    $("#motherList").innerHTML = `<article class="mother-card"><h3>母题库等待初始化</h3><p>请联系管理员完成教研数据初始化。</p></article>`;
    return;
  }
  mothers.forEach((mother) => {
    const card = document.createElement("article");
    card.className = "mother-card";
    card.innerHTML = `
      <span class="tag">${escapeHtml(mother.code)} · ${escapeHtml(mother.status)}</span>
      <h3>${escapeHtml(mother.name)}</h3>
      <p><b>解题公式：</b>${escapeHtml(mother.metadata?.formula || "待教研完善")}</p>
      <p><b>关键提醒：</b>${escapeHtml((mother.metadata?.reminders || []).join("；") || "待教研完善")}</p>
      <small>${escapeHtml(mother.metadata?.source || "来源待核验")}</small>
    `;
    $("#motherList").appendChild(card);
  });
}

async function loadAdmin() {
  const overview = await api("/api/admin/overview");
  state.adminOverview = overview;
  state.models = overview.chat_models || [];
  state.imageModels = overview.image_models || [];
  state.prompts = await api("/api/admin/prompts");
  renderKeyManager();
  renderAdminModels();
  renderAdminImageModels();
  renderImageModelSelect();
  renderPrompts();
}

function keyStatusBadge(masked) {
  return masked
    ? `<span class="key-badge key-badge-ok">已配置</span>`
    : `<span class="key-badge key-badge-missing">未配置</span>`;
}

async function updateModelKey(modelId, inputEl, buttonEl) {
  const apiKey = inputEl.value.trim();
  if (!apiKey) {
    toast("请先粘贴新的 API Key。");
    return;
  }
  const done = setBusy(buttonEl, "保存中...");
  try {
    const isImage = state.imageModels.some((m) => m.id === modelId);
    const path = isImage
      ? `/api/admin/image-models/${modelId}/api-key`
      : `/api/admin/models/${modelId}/api-key`;
    await api(path, { method: "POST", body: JSON.stringify({ api_key: apiKey }) });
    inputEl.value = "";
    await loadAdmin();
    toast("API Key 已更新。");
  } catch (err) {
    toast(err.message);
  } finally {
    done();
  }
}

function renderKeyManager() {
  const root = $("#keyManagerList");
  if (!root) return;
  root.innerHTML = "";
  const items = [
    ...(state.models || []).map((model) => ({
      id: model.id,
      name: model.name,
      provider: model.provider,
      model: model.model,
      masked: model.api_key_masked,
      isDefault: model.is_default,
      kind: "chat",
    })),
    ...(state.imageModels || []).map((model) => ({
      id: model.id,
      name: model.name,
      provider: model.provider,
      model: model.model,
      masked: model.api_key_masked,
      isDefault: model.is_default,
      kind: "image",
    })),
  ];
  if (!items.length) {
    root.innerHTML = `<p class="field-hint">暂无模型，请先在下方添加或保存模型配置。</p>`;
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "key-manager-card";
    card.innerHTML = `
      <div class="key-manager-head">
        <div>
          <strong>${escapeHtml(item.name)}</strong>
          ${item.isDefault ? `<span class="key-badge key-badge-default">默认</span>` : ""}
          ${keyStatusBadge(item.masked)}
        </div>
        <small>${escapeHtml(item.provider)} · ${escapeHtml(item.model)} · ${item.kind === "image" ? "图片" : "对话"}</small>
      </div>
      <div class="key-manager-current">${item.masked ? `当前：${escapeHtml(item.masked)}` : "当前：未配置 Key"}</div>
      <div class="key-manager-form">
        <input class="text-input key-update-input" type="password" placeholder="粘贴新的 API Key" />
        <button class="ghost-btn key-update-btn" type="button">更新 Key</button>
      </div>
    `;
    const input = card.querySelector(".key-update-input");
    const button = card.querySelector(".key-update-btn");
    button.addEventListener("click", () => updateModelKey(item.id, input, button));
    root.appendChild(card);
  });
}

function renderAdminModels() {
  const root = $("#modelAdminList");
  root.innerHTML = "";
  state.models.forEach((model) => {
    const capability = model.supports_vision ? "视觉/OCR" : "文本推理";
    const row = document.createElement("article");
    row.className = "admin-card";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(model.name)}</strong>
        <small>${escapeHtml(model.provider)} · ${escapeHtml(model.model)} · ${escapeHtml(capability)} · ${escapeHtml(model.api_key_masked || "未配置Key")}</small>
      </div>
      <div class="admin-actions">
        <button class="ghost-btn test-model" type="button">测试连接</button>
        <button class="ghost-btn edit-model" type="button">编辑</button>
        <button class="ghost-btn default-model" type="button">${model.is_default ? "默认" : "设默认"}</button>
      </div>
    `;
    row.querySelector(".test-model").addEventListener("click", async () => {
      const button = row.querySelector(".test-model");
      const done = setBusy(button, "测试中...");
      try {
        const result = await api(`/api/admin/models/${model.id}/test`, { method: "POST", body: "{}" });
        toast(result.ok ? `连接成功：${result.sample || "OK"}` : result.message || "连接失败");
      } catch (err) {
        toast(err.message);
      } finally {
        done();
      }
    });
    row.querySelector(".edit-model").addEventListener("click", () => fillModelForm(model));
    row.querySelector(".default-model").addEventListener("click", async () => {
      await api("/api/admin/default-model", { method: "POST", body: JSON.stringify({ id: model.id }) });
      await loadModels();
      await loadAdmin();
      toast("默认模型已更新。");
    });
    root.appendChild(row);
  });
}

function fillModelForm(model) {
  $("#modelIdInput").value = model.id;
  $("#modelNameInput").value = model.name;
  $("#providerInput").value = model.provider;
  $("#endpointInput").value = model.endpoint;
  $("#modelNameApiInput").value = model.model;
  $("#apiKeyInput").value = "";
  $("#temperatureInput").value = model.temperature;
  $("#maxTokensInput").value = model.max_tokens;
  $("#visionInput").checked = Boolean(model.supports_vision);
}

function fillModelPreset(type) {
  if (type === "deepseek") {
    $("#modelIdInput").value = "deepseek-reasoner-default";
    $("#modelNameInput").value = "DeepSeek 拆题增强";
    $("#providerInput").value = "deepseek";
    $("#endpointInput").value = "https://api.deepseek.com/chat/completions";
    $("#modelNameApiInput").value = "deepseek-chat";
    $("#apiKeyInput").value = "";
    $("#temperatureInput").value = 0.25;
    $("#maxTokensInput").value = 8000;
    $("#visionInput").checked = false;
    toast("已填入 DeepSeek 推理模型模板，粘贴 Key 后保存。");
    return;
  }
  if (type === "fenno") {
    $("#modelIdInput").value = "fenno-gpt-default";
    $("#modelNameInput").value = "Fenno GPT-5.4 拆题增强";
    $("#providerInput").value = "fenno";
    $("#endpointInput").value = "https://api.fenno.ai";
    $("#modelNameApiInput").value = "gpt-5.4";
    $("#apiKeyInput").value = "";
    $("#temperatureInput").value = 0.35;
    $("#maxTokensInput").value = 8000;
    $("#visionInput").checked = false;
    toast("已填入 Fenno 模板：Base URL 保持 https://api.fenno.ai 即可，后端会自动使用 /v1/chat/completions。");
    return;
  }
  $("#modelIdInput").value = "minimax-m3-default";
  $("#modelNameInput").value = "MiniMax M3 视觉 OCR";
  $("#providerInput").value = "minimax";
  $("#endpointInput").value = "https://api.minimax.chat/v1/chat/completions";
  $("#modelNameApiInput").value = "MiniMax-M3";
  $("#apiKeyInput").value = "";
  $("#temperatureInput").value = 0.45;
  $("#maxTokensInput").value = 7000;
  $("#visionInput").checked = true;
  toast("已填入 MiniMax 视觉 OCR 模板。");
}

function renderAdminImageModels() {
  const root = $("#imageModelAdminList");
  if (!root) return;
  root.innerHTML = "";
  state.imageModels.forEach((model) => {
    const row = document.createElement("article");
    row.className = "admin-card";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(model.name)}</strong>
        <small>${escapeHtml(model.provider)} · ${escapeHtml(model.model)} · ${escapeHtml(model.size)} · ${escapeHtml(model.quality)} · ${escapeHtml(model.api_key_masked || "未配置Key")}</small>
      </div>
      <div class="admin-actions">
        <button class="ghost-btn edit-image-model" type="button">编辑</button>
        <button class="ghost-btn default-image-model" type="button">${model.is_default ? "默认" : "设默认"}</button>
      </div>
    `;
    row.querySelector(".edit-image-model").addEventListener("click", () => fillImageModelForm(model));
    row.querySelector(".default-image-model").addEventListener("click", async () => {
      await api("/api/admin/default-image-model", { method: "POST", body: JSON.stringify({ id: model.id }) });
      await loadImageModels();
      await loadAdmin();
      toast("默认图片模型已更新。");
    });
    root.appendChild(row);
  });
}

function fillImageModelForm(model) {
  $("#imageModelIdInput").value = model.id;
  $("#imageModelNameInput").value = model.name;
  $("#imageProviderInput").value = model.provider;
  $("#imageEndpointInput").value = model.endpoint;
  $("#imageModelNameApiInput").value = model.model;
  $("#imageApiKeyInput").value = "";
  $("#imageSizeInput").value = model.size || "1024x1536";
  $("#imageQualityInput").value = model.quality || "high";
}

function fillImageModelPreset() {
  $("#imageModelIdInput").value = "openai-gpt-image-default";
  $("#imageModelNameInput").value = "OpenAI GPT Image 卡片生成";
  $("#imageProviderInput").value = "openai";
  $("#imageEndpointInput").value = "https://api.openai.com/v1/images/generations";
  $("#imageModelNameApiInput").value = "gpt-image-1.5";
  $("#imageApiKeyInput").value = "";
  $("#imageSizeInput").value = "1024x1536";
  $("#imageQualityInput").value = "high";
  toast("已填入 OpenAI 图片生成模板；如账号已开通 gpt-image-2，可把模型名改成 gpt-image-2。");
}

function fillFennoImageModelPreset() {
  $("#imageModelIdInput").value = "fenno-gpt-image-default";
  $("#imageModelNameInput").value = "Fenno GPT-Image2 卡片生成";
  $("#imageProviderInput").value = "fenno";
  $("#imageEndpointInput").value = "https://api.fenno.ai";
  $("#imageModelNameApiInput").value = "gpt-image-2";
  $("#imageApiKeyInput").value = "";
  $("#imageSizeInput").value = "1024x1536";
  $("#imageQualityInput").value = "medium";
  toast("已填入 Fenno GPT-Image2 模板：Base URL 保持 https://api.fenno.ai 即可，后端会自动使用 /v1/images/generations。");
}

function renderPrompts() {
  const select = $("#promptSelect");
  select.innerHTML = "";
  state.prompts.forEach((prompt) => {
    const option = document.createElement("option");
    option.value = prompt.key;
    option.textContent = prompt.name;
    select.appendChild(option);
  });
  if (state.prompts[0]) {
    select.value = state.prompts[0].key;
    $("#promptContent").value = state.prompts[0].content;
  }
}

function switchView(view) {
  if (view === "admin" && !state.user?.is_admin) {
    toast("请使用管理员账号登录后访问后台配置。");
    view = "portal";
  }
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $$(".view").forEach((item) => item.classList.remove("active"));
  const target = $(`#view-${view}`);
  if (!target) return;
  target.classList.add("active");
  if (view === "portal") {
    if (!state.portalTools.length) loadPortalTools().catch((err) => toast(err.message));
    updateAccountCard();
    renderTodayPanel().catch(() => {});
  }
  if (view === "tool") {
    if (!state.portalTools.length) loadPortalTools().catch((err) => toast(err.message));
    updateToolRunner();
  }
  if (view === "agent") {
    loadAgentLayers().catch((err) => toast(err.message));
    loadRagDocuments().catch((err) => toast(err.message));
  }
  if (view === "history") loadHistory().catch((err) => toast(err.message));
  if (view === "library") loadLibrary().catch((err) => toast(err.message));
  if (view === "report") loadReport().catch((err) => toast(err.message));
  if (view === "profile") loadProfile().catch((err) => toast(err.message));
  if (view === "mothers") loadMothers().catch((err) => toast(err.message));
  if (view === "admin") loadAdmin().catch((err) => toast(err.message));
}

function bindEvents() {
  $$(".nav-item").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  $("#portalStartBtn")?.addEventListener("click", () => switchView("diagnose"));
  $("#portalLibraryBtn")?.addEventListener("click", () => switchView("library"));
  $("#convertLatexBtn")?.addEventListener("click", convertLatexInput);
  $("#downloadLatexBtn")?.addEventListener("click", downloadLastLatex);
  $("#refreshTodayBtn")?.addEventListener("click", () => renderTodayPanel().catch((err) => toast(err.message)));
  $("#studentModeToggle")?.addEventListener("change", (event) => {
    state.studentMode = event.target.checked;
    applyStudentMode();
  });
  $("#scrollToTrainingBtn")?.addEventListener("click", () => {
    if (state.variants.length) {
      renderVariants(state.variants);
      $("#trainingPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    toast("巩固题生成中或尚未返回，请稍后重试。");
  });
  $("#guestLoginBtn")?.addEventListener("click", () => openModal("authModal"));
  $("#questionText")?.addEventListener("input", () => {
    setCalibrationBanner(questionNeedsCalibration($("#questionText").value.trim(), state.ocrConfidence));
  });
  $$("[data-goto-view]").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.gotoView));
  });
  $("#contactBtn")?.addEventListener("click", () => openModal("contactModal"));
  $("#toolSelect")?.addEventListener("change", () => {
    state.activeToolId = $("#toolSelect").value;
    updateToolRunner();
  });
  $("#runToolBtn")?.addEventListener("click", runTool);
  $("#copyToolOutputBtn")?.addEventListener("click", copyToolOutput);
  $("#runAgentBtn")?.addEventListener("click", runAgentSolve);
  $("#agentSampleBtn")?.addEventListener("click", fillAgentSample);
  $("#copyAgentResultBtn")?.addEventListener("click", copyAgentResult);
  $("#saveRagDocBtn")?.addEventListener("click", saveRagDocument);
  $("#searchRagBtn")?.addEventListener("click", () => searchRagForCurrentQuestion());
  $("#generateRagQuizBtn")?.addEventListener("click", generateRagQuiz);
  $("#buildRagStudyBtn")?.addEventListener("click", buildRagStudyOs);
  $("#refreshHistoryBtn")?.addEventListener("click", () => loadHistory().catch((err) => toast(err.message)));
  $("#authSubmitBtn")?.addEventListener("click", submitAuth);
  $("#redeemSubmitBtn")?.addEventListener("click", submitRedeem);
  $$(".modal-tab").forEach((button) => button.addEventListener("click", () => setAuthMode(button.dataset.authMode)));
  $$("[data-close-modal]").forEach((button) => button.addEventListener("click", () => closeModal(button.dataset.closeModal)));
  $$(".terms-link").forEach((button) => button.addEventListener("click", () => showTerms(button.dataset.terms)));
  $$(".modal-overlay").forEach((overlay) => overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeModal(overlay.id);
  }));
  $$(".input-mode").forEach((button) => button.addEventListener("click", () => setInputMode(button.dataset.inputMode)));
  $$(".flow-task").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.scrollTarget);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  $("#modelSelect").addEventListener("change", () => {
    state.selectedModelId = selectedModelId();
    toast("前台模型已切换。");
  });

  $("#imageModelSelect").addEventListener("change", () => {
    state.selectedImageModelId = selectedImageModelId();
    toast("图片生成模型已切换。");
  });

  $("#imageInput").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      state.imageDataUrl = reader.result;
      $("#previewImage").src = reader.result;
      $("#previewImage").classList.remove("hidden");
      state.ocrText = "";
      setInputMode("image");
    };
    reader.readAsDataURL(file);
  });

  $("#sampleBtn").addEventListener("click", () => {
    setInputMode("paste");
    $("#subjectSelect").value = "高中数学";
    $("#questionText").value = "已知数列 a_n = 1/[n(n+2)]，求数列前 n 项和 S_n。";
    $("#wrongAnswer").value = "学生作答：a_n = 1/n - 1/(n+2)，所以 S_n = 1 - 1/(n+2)。\n批注：忘记乘 1/2，且首尾剩余项漏了 1/2 和 1/(n+1)。";
  });

  $("#ocrBtn").addEventListener("click", runOcr);
  $("#analyzePaperBtn")?.addEventListener("click", createPaperAnalysis);
  $("#refreshPapersBtn")?.addEventListener("click", () => loadPapers().catch((err) => toast(err.message)));
  $("#diagnoseBtn").addEventListener("click", diagnose);
  $("#generateStudyCardBtn").addEventListener("click", generateStudyCard);
  updateDiagnoseProgress("input");

  $("#refreshLibraryBtn").addEventListener("click", () => loadLibrary().catch((err) => toast(err.message)));
  $("#refreshProfileBtn").addEventListener("click", () => loadProfile().catch((err) => toast(err.message)));
  $("#createShareBtn")?.addEventListener("click", createProfileShare);
  $("#archiveSubjectSelect").addEventListener("change", renderArchiveList);
  $("#applyBulkFieldsBtn").addEventListener("click", applyBulkFields);
  $("#exportProfileBtn").addEventListener("click", exportProfile);
  $("#reloadAdminBtn").addEventListener("click", () => loadAdmin().catch((err) => toast(err.message)));
  $("#presetMinimaxBtn").addEventListener("click", () => fillModelPreset("minimax"));
  $("#presetDeepseekBtn").addEventListener("click", () => fillModelPreset("deepseek"));
  $("#presetFennoBtn").addEventListener("click", () => fillModelPreset("fenno"));
  $("#presetImageBtn").addEventListener("click", fillImageModelPreset);
  $("#presetFennoImageBtn").addEventListener("click", fillFennoImageModelPreset);

  $("#saveModelBtn").addEventListener("click", async () => {
    const done = setBusy($("#saveModelBtn"), "保存中...");
    try {
      const payload = {
        id: $("#modelIdInput").value || undefined,
        name: $("#modelNameInput").value || "MiniMax M3",
        provider: $("#providerInput").value || "minimax",
        endpoint: $("#endpointInput").value || "https://api.minimax.chat/v1/chat/completions",
        model: $("#modelNameApiInput").value || "MiniMax-M3",
        api_key: $("#apiKeyInput").value,
        supports_vision: $("#visionInput").checked,
        temperature: Number($("#temperatureInput").value || 0.45),
        max_tokens: Number($("#maxTokensInput").value || 7000),
      };
      await api("/api/admin/models", { method: "POST", body: JSON.stringify(payload) });
      $("#apiKeyInput").value = "";
      await loadModels();
      await loadAdmin();
      toast("模型已保存。");
    } catch (err) {
      toast(err.message);
    } finally {
      done();
    }
  });

  $("#saveImageModelBtn").addEventListener("click", async () => {
    const done = setBusy($("#saveImageModelBtn"), "保存中...");
    try {
      const payload = {
        id: $("#imageModelIdInput").value || undefined,
        name: $("#imageModelNameInput").value || "OpenAI GPT Image 卡片生成",
        provider: $("#imageProviderInput").value || "openai",
        endpoint: $("#imageEndpointInput").value || "https://api.openai.com/v1/images/generations",
        model: $("#imageModelNameApiInput").value || "gpt-image-1.5",
        api_key: $("#imageApiKeyInput").value,
        size: $("#imageSizeInput").value || "1024x1536",
        quality: $("#imageQualityInput").value || "high",
      };
      await api("/api/admin/image-models", { method: "POST", body: JSON.stringify(payload) });
      $("#imageApiKeyInput").value = "";
      await loadImageModels();
      await loadAdmin();
      toast("图片模型已保存。");
    } catch (err) {
      toast(err.message);
    } finally {
      done();
    }
  });

  $("#promptSelect").addEventListener("change", () => {
    const prompt = state.prompts.find((item) => item.key === $("#promptSelect").value);
    $("#promptContent").value = prompt?.content || "";
  });

  $("#savePromptBtn").addEventListener("click", async () => {
    const done = setBusy($("#savePromptBtn"), "保存中...");
    try {
      await api("/api/admin/prompts", {
        method: "POST",
        body: JSON.stringify({ key: $("#promptSelect").value, content: $("#promptContent").value }),
      });
      await loadAdmin();
      toast("提示词已保存。");
    } catch (err) {
      toast(err.message);
    } finally {
      done();
    }
  });
}

prepareChineseWorkbench();
bindEvents();
bindDashboard();
setInputMode("image");
setAuthMode("login");
bindAllFileIngests();
state.studentMode = localStorage.getItem(STUDENT_MODE_KEY) !== "0";
applyStudentMode();
captureUnifiedTokenFromUrl();
loadAppConfig().then(loadUser).catch((err) => toast(err.message));
loadPortalTools().catch((err) => toast(err.message));
loadInstitutions().catch((err) => toast(err.message));
loadAgentLayers().catch((err) => toast(err.message));
loadModels().catch((err) => toast(err.message));
loadImageModels().catch((err) => toast(err.message));
loadPapers().catch(() => {});
