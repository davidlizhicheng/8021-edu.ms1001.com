(function () {
  const msg = document.getElementById("msg");
  const gate = document.getElementById("gate");
  const registerPanel = document.getElementById("register-panel");
  const workspace = document.getElementById("workspace");

  function toast(text, ok) {
    msg.style.display = "block";
    msg.style.background = ok ? "#e8f5e9" : "#fdecea";
    msg.style.color = ok ? "#1b5e20" : "#8f1717";
    msg.textContent = text;
  }

  function token() {
    const hash = new URLSearchParams(location.hash.replace(/^#/, ""));
    const query = new URLSearchParams(location.search);
    const incoming = hash.get("access_token") || hash.get("token") || query.get("access_token") || query.get("token");
    if (incoming) {
      localStorage.setItem("suat_access_token", incoming);
      history.replaceState(null, "", location.pathname);
    }
    return incoming || localStorage.getItem("suat_access_token") || localStorage.getItem("suat_token") || localStorage.getItem("token") || "";
  }

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function api(path, opts) {
    const headers = { "Content-Type": "application/json" };
    const t = token();
    if (t) headers.Authorization = "Bearer " + t;
    const res = await fetch(path, { ...opts, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  function renderStaff(inst) {
    document.getElementById("staff-list").innerHTML = (inst.admin_usernames || [])
      .map((u) => `<span class="staff-tag">${u}${u === inst.owner ? " · 负责人" : ""}</span>`)
      .join("");
  }

  function fill(inst) {
    document.getElementById("org-name").textContent = inst.name;
    document.getElementById("org-meta").textContent = `slug：${inst.slug} · 状态：${inst.status || "active"}`;
    const f = document.getElementById("org-form");
    f.name.value = inst.name || "";
    f.city.value = inst.city || "";
    f.contact_name.value = inst.contact_name || "";
    f.contact_phone.value = inst.contact_phone || "";
    f.intro.value = inst.intro || "";
    f.class_count.value = inst.class_count || 0;
    renderStaff(inst);
  }

  function renderMembers(members) {
    const box = document.getElementById("member-list");
    if (!box) return;
    if (!members?.length) {
      box.innerHTML = "<p>暂无机构成员。</p>";
      return;
    }
    box.innerHTML = `<table class="member-table">
      <thead><tr><th>成员</th><th>归属</th><th>备注</th><th>操作</th></tr></thead>
      <tbody>${members.map((m) => `<tr>
        <td><strong>${esc(m.name || m.username)}</strong><br>${esc([m.role, m.grade, m.class_name, m.phone].filter(Boolean).join(" · "))}</td>
        <td><span class="staff-tag">${esc(m.institution_badge || m.institution_name || "本机构")}</span></td>
        <td>${esc(m.note || "")}</td>
        <td><button type="button" class="btn btn-primary btn-remove-member" data-id="${esc(m.id)}">移出</button></td>
      </tr>`).join("")}</tbody>
    </table>`;
    box.querySelectorAll(".btn-remove-member").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("确认将该成员移出本机构？")) return;
        try {
          const data = await api(`/api/org/members/${encodeURIComponent(btn.dataset.id)}/delete`, { method: "POST" });
          renderMembers(data.members || []);
          if (data.institution) fill(data.institution);
          toast("已移出机构", true);
        } catch (err) {
          toast(err.message, false);
        }
      });
    });
  }

  async function loadMembers() {
    try {
      const data = await api("/api/org/members");
      renderMembers(data.members || []);
    } catch (err) {
      const box = document.getElementById("member-list");
      if (box) box.innerHTML = `<p>${esc(err.message)}</p>`;
    }
  }

  async function boot() {
    if (!token()) return;
    try {
      const data = await api("/api/org/me");
      gate.hidden = true;
      registerPanel.hidden = true;
      workspace.hidden = false;
      fill(data.institution);
      loadMembers();
    } catch (e) {
      if (String(e.message).includes("尚未注册") || String(e.message).includes("404")) {
        gate.hidden = true;
        registerPanel.hidden = false;
      } else {
        toast(e.message, false);
      }
    }
  }

  document.getElementById("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    try {
      await api("/api/org/register", { method: "POST", body: JSON.stringify(body) });
      toast("机构注册成功", true);
      boot();
    } catch (err) {
      toast(err.message, false);
    }
  });

  document.getElementById("org-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    body.class_count = Number(body.class_count || 0);
    try {
      const data = await api("/api/org/me", { method: "POST", body: JSON.stringify(body) });
      fill(data.institution);
      toast("已保存", true);
    } catch (err) {
      toast(err.message, false);
    }
  });

  document.getElementById("staff-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = new FormData(e.target).get("username");
    try {
      const cur = await api("/api/org/me");
      const admins = [...new Set([...(cur.institution.admin_usernames || []), String(username).trim()])];
      const data = await api("/api/org/me", {
        method: "POST",
        body: JSON.stringify({ admin_usernames: admins }),
      });
      fill(data.institution);
      e.target.reset();
      toast("已添加协作账号", true);
    } catch (err) {
      toast(err.message, false);
    }
  });

  document.getElementById("member-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    try {
      const data = await api("/api/org/members", { method: "POST", body: JSON.stringify(body) });
      renderMembers(data.members || []);
      if (data.institution) fill(data.institution);
      e.target.reset();
      toast("机构成员已保存", true);
    } catch (err) {
      toast(err.message, false);
    }
  });

  boot();
})();
