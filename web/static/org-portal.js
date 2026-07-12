(function (global) {
  function esc(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderOrgPortal(config) {
    const cfg = config || {};
    const brand = cfg.brand || {};
    const cards = cfg.cards || [];
    const actions = cfg.actions || [];
    const panel = cfg.panel || {};

    document.title = brand.title ? `${brand.title} | 机构站点` : "机构站点";
    const root = document.getElementById("org-portal-root");
    if (!root) return;

    const actionHtml = actions
      .map(
        (a) =>
          `<a class="org-btn ${a.primary ? "org-btn-primary" : "org-btn-ghost"}" href="${esc(a.href)}">${esc(a.label)}</a>`,
      )
      .join("");

    const cardHtml = cards
      .map(
        (c) => `<article class="org-card">
        <h3>${esc(c.title)}</h3>
        <p>${esc(c.desc)}</p>
        ${c.href ? `<a href="${esc(c.href)}">${esc(c.cta || "了解更多 →")}</a>` : ""}
      </article>`,
      )
      .join("");

    const navHtml = (cfg.nav || [])
      .map((n) => `<a href="${esc(n.href)}">${esc(n.label)}</a>`)
      .join("");

    root.innerHTML = `
      <header class="org-topbar">
        <div class="org-topbar-inner">
          <a class="org-brand" href="${esc(brand.homeHref || "/")}">
            <span class="org-brand-mark">${esc(brand.mark || "MS")}</span>
            <span>
              <div class="org-brand-title">${esc(brand.title || "机构站点")}</div>
              <div class="org-brand-sub">${esc(brand.subtitle || "")}</div>
            </span>
          </a>
          <nav class="org-topnav">${navHtml}</nav>
        </div>
      </header>
      <main class="org-wrap">
        <section class="org-hero">
          <div class="org-hero-main">
            <p class="org-kicker">${esc(brand.kicker || "INSTITUTION PORTAL")}</p>
            <h1>${esc(brand.headline || brand.title || "机构入驻与站点管理")}</h1>
            <p class="org-lead">${esc(brand.lead || "")}</p>
            <div class="org-actions">${actionHtml}</div>
          </div>
          <aside class="org-panel">
            <h2>${esc(panel.title || "机构能做什么")}</h2>
            <p>${esc(panel.desc || "")}</p>
            ${panel.items?.length ? `<ul>${panel.items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
          </aside>
        </section>
        <section class="org-grid">${cardHtml}</section>
        <footer class="org-footer">${esc(cfg.footer || "MS1001 · 统一账号 · 机构站点模板")}</footer>
      </main>`;
  }

  global.MS1001OrgPortal = { renderOrgPortal, esc };
})(window);
