(() => {
  "use strict";

  const GRUPO_DESC = {
    "Grupo A": "Matriz por estágio — Operador e App",
    "Grupo B": "Regressão — pendências reportadas em 02/07",
    "Grupo C": "Evolução da semana — itens transversais",
    "Grupo D": "Ticket filho — a detalhar antes de testar",
  };
  const STATUSES = ["Não testado", "Aprovado", "Reprovado", "Bloqueado", "N/A"];
  const STATUS_CODE = { "Não testado": "nt", "Aprovado": "ok", "Reprovado": "bad", "Bloqueado": "warn", "N/A": "na" };
  const FRONT_CODE = { "App do técnico": "app", "Operador (web)": "opr", "Transversal": "trv", "A definir": "trv" };
  const TESTER_KEY = "fluxoc_tester_name";

  let CASES = [];
  const activeFilters = { grupo: "", estagio: "", frente: "", status: "" };

  const FRENT_CHIP_CLASS = { "App do técnico": "c-app", "Operador (web)": "c-opr", "Transversal": "c-trv", "A definir": "c-trv" };
  const STATUS_CHIP_CLASS = { "Não testado": "c-nt", "Aprovado": "c-ok", "Reprovado": "c-bad", "Bloqueado": "c-warn", "N/A": "c-na" };

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const esc = (s) => (s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function toast(msg, isError) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.toggle("error", !!isError);
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.hidden = true; }, 2200);
  }

  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (e) {}
      throw new Error(detail);
    }
    const ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : res;
  }

  function testerName() {
    return $("#input-tester").value.trim() || localStorage.getItem(TESTER_KEY) || "";
  }

  // ---------------- load ----------------
  async function loadCases() {
    CASES = await api("/api/cases");
    $("#cases-loading").hidden = true;
    buildFilters();
    render();
  }

  function buildFilters() {
    const uniq = (arr) => [...new Set(arr)];
    buildChipGroup("chips-grupo", "grupo", ["Todos", ...uniq(CASES.map((c) => c.grupo))]);
    buildChipGroup("chips-frente", "frente", ["Todas", ...uniq(CASES.map((c) => c.frente))], FRENT_CHIP_CLASS);
    buildChipGroup("chips-status", "status", ["Todos", ...STATUSES], STATUS_CHIP_CLASS);
    buildChipGroup("chips-estagio", "estagio", ["Todos", ...uniq(CASES.map((c) => c.estagio))]);
  }

  function buildChipGroup(containerId, filterKey, values, colorMap) {
    const el = document.getElementById(containerId);
    el.innerHTML = values.map((v, i) => {
      const isAll = i === 0;
      const val = isAll ? "" : v;
      const colorClass = colorMap && colorMap[v] ? colorMap[v] : "";
      const active = activeFilters[filterKey] === val;
      return `<button type="button" class="chip ${colorClass} ${active ? "active" : ""}" data-key="${filterKey}" data-val="${esc(val)}">${esc(v)}</button>`;
    }).join("");
    $$(".chip", el).forEach((btn) => {
      btn.addEventListener("click", () => {
        activeFilters[btn.dataset.key] = btn.dataset.val;
        $$(".chip", el).forEach((b) => b.classList.toggle("active", b.dataset.val === btn.dataset.val));
        applyFilters();
      });
    });
  }

  // ---------------- render ----------------
  function shotThumb(shot, code) {
    return `<div class="shot-thumb" data-shot="${shot.id}">
      <img src="/api/screenshots/${shot.id}" alt="${esc(shot.filename)}" loading="lazy">
      <button class="del" data-del-shot="${shot.id}" data-code="${code}" title="Remover print">✕</button>
    </div>`;
  }

  function caseCard(c) {
    const stCode = STATUS_CODE[c.status] || "nt";
    const frontCode = FRONT_CODE[c.frente] || "trv";
    const shots = (c.screenshots || []).map((s) => shotThumb(s, c.code)).join("");
    return `<article class="case st-${stCode}" data-code="${c.code}"
        data-grupo="${esc(c.grupo)}" data-estagio="${esc(c.estagio)}" data-frente="${esc(c.frente)}" data-status="${esc(c.status)}"
        data-search="${esc((c.code + " " + c.resultado_esperado + " " + c.estagio).toLowerCase())}">
      <div class="case-head">
        <span class="case-code">${esc(c.code)}</span>
        <span class="tag front-${frontCode}">${esc(c.frente)}</span>
        <span class="tag">${esc(c.estagio)}</span>
        <span class="tag prio-${esc(c.prioridade)}">${esc(c.prioridade)}</span>
      </div>
      <div class="case-grid">
        <div class="blk"><div class="k">Pré-condição</div><div class="v">${esc(c.pre_condicao)}</div></div>
        <div class="blk"><div class="k">Passos</div><div class="v">${esc(c.passos)}</div></div>
        <div class="blk wide result"><div class="k">Resultado esperado</div><div class="v">${esc(c.resultado_esperado)}</div></div>
      </div>
      <div class="case-foot">
        <div class="status-row">
          <div class="status-btns">
            ${STATUSES.map((s) => `<button class="sbtn ${s === c.status ? "active" : ""}" data-s="${s}">${s}</button>`).join("")}
          </div>
        </div>
        <div class="obs-row">
          <textarea class="obs-input" rows="1" placeholder="Observação...">${esc(c.observacao || "")}</textarea>
        </div>
        <div class="shots-row">
          <div class="shots-grid">${shots}</div>
          <label class="upload-zone" title="Anexar print">
            +
            <input type="file" accept="image/*" class="shot-input">
          </label>
        </div>
      </div>
    </article>`;
  }

  function render() {
    const order = ["Grupo A", "Grupo B", "Grupo C", "Grupo D"];
    const groups = {};
    CASES.forEach((c) => { (groups[c.grupo] = groups[c.grupo] || []).push(c); });
    let html = "";
    order.filter((g) => groups[g]).forEach((g) => {
      html += `<div class="grp-heading"><span class="badge">${g}</span><span class="desc">${GRUPO_DESC[g] || ""}</span></div>`;
      html += groups[g].map(caseCard).join("");
    });
    $("#cases").innerHTML = html;
    attachCardHandlers();
    applyFilters();
    updateStats();
  }

  function findCase(code) { return CASES.find((c) => c.code === code); }

  function patchCaseLocal(code, patch) {
    const c = findCase(code);
    Object.assign(c, patch);
    return c;
  }

  // ---------------- handlers ----------------
  function attachCardHandlers() {
    $$(".case").forEach((card) => {
      const code = card.dataset.code;

      $$(".sbtn", card).forEach((btn) => {
        btn.addEventListener("click", async () => {
          const s = btn.dataset.s;
          $$(".sbtn", card).forEach((b) => b.classList.toggle("active", b.dataset.s === s));
          card.className = card.className.replace(/\bst-\w+\b/, "") + ` st-${STATUS_CODE[s]}`;
          card.dataset.status = s;
          try {
            const updated = await api(`/api/cases/${encodeURIComponent(code)}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ status: s, testado_por: testerName() || undefined }),
            });
            patchCaseLocal(code, updated);
            updateStats();
            toast(`${code} → ${s}`);
          } catch (e) { toast("Erro ao salvar: " + e.message, true); }
        });
      });

      const obs = $(".obs-input", card);
      let obsTimer = null;
      obs.addEventListener("input", () => {
        clearTimeout(obsTimer);
        obsTimer = setTimeout(async () => {
          try {
            const updated = await api(`/api/cases/${encodeURIComponent(code)}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ observacao: obs.value, testado_por: testerName() || undefined }),
            });
            patchCaseLocal(code, updated);
            toast("Observação salva");
          } catch (e) { toast("Erro ao salvar observação: " + e.message, true); }
        }, 700);
      });

      const fileInput = $(".shot-input", card);
      const zone = $(".upload-zone", card);
      fileInput.addEventListener("change", () => { if (fileInput.files[0]) uploadShot(code, fileInput.files[0], card); });
      ["dragover", "dragenter"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("dragover"); }));
      ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("dragover"); }));
      zone.addEventListener("drop", (e) => {
        const f = e.dataTransfer.files[0];
        if (f) uploadShot(code, f, card);
      });

      $$(".shots-grid .shot-thumb img", card).forEach((img) => {
        img.addEventListener("click", () => openLightbox(img.src));
      });
      $$(".del[data-del-shot]", card).forEach((btn) => {
        btn.addEventListener("click", async (e) => {
          e.stopPropagation();
          if (!confirm("Remover este print?")) return;
          try {
            const updated = await api(`/api/screenshots/${btn.dataset.delShot}`, { method: "DELETE" });
            patchCaseLocal(code, updated);
            rerenderCard(code);
            toast("Print removido");
          } catch (err) { toast("Erro ao remover: " + err.message, true); }
        });
      });
    });
  }

  function rerenderCard(code) {
    const c = findCase(code);
    const old = document.querySelector(`.case[data-code="${cssEscape(code)}"]`);
    if (!old || !c) return;
    const wrap = document.createElement("div");
    wrap.innerHTML = caseCard(c);
    const fresh = wrap.firstElementChild;
    old.replaceWith(fresh);
    attachCardHandlers();
    applyFilters();
  }

  function cssEscape(s) { return s.replace(/[^a-zA-Z0-9_-]/g, (c) => "\\" + c); }

  async function uploadShot(code, file, card) {
    const zone = $(".upload-zone", card);
    zone.textContent = "…";
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (testerName()) fd.append("uploaded_by", testerName());
      const updated = await api(`/api/cases/${encodeURIComponent(code)}/screenshots`, { method: "POST", body: fd });
      patchCaseLocal(code, updated);
      rerenderCard(code);
      toast("Print anexado");
    } catch (e) {
      toast("Erro ao subir print: " + e.message, true);
      zone.textContent = "+";
    }
  }

  function openLightbox(src) {
    $("#lightbox-img").src = src;
    $("#lightbox").hidden = false;
  }
  $("#lightbox-close").addEventListener("click", () => { $("#lightbox").hidden = true; });
  $("#lightbox").addEventListener("click", (e) => { if (e.target.id === "lightbox") $("#lightbox").hidden = true; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#lightbox").hidden = true; });

  // ---------------- filters ----------------
  function applyFilters() {
    const { grupo: g, estagio: e, frente: fr, status: st } = activeFilters;
    const q = $("#f-busca").value.trim().toLowerCase();
    $$(".case").forEach((card) => {
      let ok = true;
      if (g && card.dataset.grupo !== g) ok = false;
      if (e && card.dataset.estagio !== e) ok = false;
      if (fr && card.dataset.frente !== fr) ok = false;
      if (st && card.dataset.status !== st) ok = false;
      if (q && !card.dataset.search.includes(q)) ok = false;
      card.classList.toggle("hidden", !ok);
    });
  }
  $("#f-busca").addEventListener("input", applyFilters);

  // ---------------- stats ----------------
  function updateStats() {
    const counts = { "Não testado": 0, "Aprovado": 0, "Reprovado": 0, "Bloqueado": 0, "N/A": 0 };
    CASES.forEach((c) => { counts[c.status] = (counts[c.status] || 0) + 1; });
    $("#stat-nt").textContent = counts["Não testado"];
    $("#stat-ok").textContent = counts["Aprovado"];
    $("#stat-bad").textContent = counts["Reprovado"];
    $("#stat-warn").textContent = counts["Bloqueado"];
    $("#stat-na").textContent = counts["N/A"];
    const total = CASES.length || 1;
    const executado = total - counts["Não testado"];
    const pct = Math.round((executado / total) * 100);
    $("#hero-pct").textContent = pct + "%";
    $("#pbar-fill").style.width = pct + "%";
  }

  // ---------------- tester name ----------------
  const testerInput = $("#input-tester");
  testerInput.value = localStorage.getItem(TESTER_KEY) || "";
  testerInput.addEventListener("change", () => localStorage.setItem(TESTER_KEY, testerInput.value.trim()));

  // ---------------- boot ----------------
  loadCases().catch((e) => {
    $("#cases-loading").textContent = "Erro ao carregar casos: " + e.message;
  });
})();
