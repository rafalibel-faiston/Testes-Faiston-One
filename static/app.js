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

  function fmtWhen(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

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
    render();
  }

  function buildFilters(list) {
    const src = list || CASES;
    const uniq = (arr) => [...new Set(arr)];
    buildChipGroup("chips-grupo", "grupo", ["Todos", ...uniq(src.map((c) => c.grupo))]);
    buildChipGroup("chips-frente", "frente", ["Todas", ...uniq(src.map((c) => c.frente))], FRENT_CHIP_CLASS);
    buildChipGroup("chips-status", "status", ["Todos", ...STATUSES], STATUS_CHIP_CLASS);
    buildChipGroup("chips-estagio", "estagio", ["Todos", ...uniq(src.map((c) => c.estagio))]);
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

  function obsList(observations) {
    if (!observations || !observations.length) {
      return `<div class="obs-empty">Nenhuma observação ainda.</div>`;
    }
    return observations.map((o) => `<div class="obs-item">
        <div class="obs-item-head"><span class="obs-author">${esc(o.autor || "Anônimo")}</span><span class="obs-when">${fmtWhen(o.created_at)}</span></div>
        <div class="obs-text">${esc(o.texto)}</div>
      </div>`).join("");
  }

  function caseCard(c) {
    const stCode = STATUS_CODE[c.status] || "nt";
    const frontCode = FRONT_CODE[c.frente] || "trv";
    const shots = (c.screenshots || []).map((s) => shotThumb(s, c.code)).join("");
    // numero curto e estavel: pega o sufixo do codigo (ex.: FC-02-APP-01 -> 1)
    // em vez de um indice global, que por coincidencia podia parecer o numero do estagio.
    const seqMatch = c.code.match(/-(\d+)$/);
    const idx = seqMatch ? parseInt(seqMatch[1], 10) : (CASES.indexOf(c) + 1);
    return `<article class="case st-${stCode}" data-code="${c.code}"
        data-grupo="${esc(c.grupo)}" data-estagio="${esc(c.estagio)}" data-frente="${esc(c.frente)}" data-status="${esc(c.status)}"
        data-search="${esc((c.code + " " + c.resultado_esperado + " " + c.estagio).toLowerCase())}">
      <div class="case-head">
        <span class="case-num">Teste ${idx}</span>
        <span class="tag front-${frontCode}">${esc(c.frente)}</span>
        <span class="tag">${esc(c.estagio)}</span>
        <span class="tag prio-${esc(c.prioridade)}">${esc(c.prioridade)}</span>
        ${c.user_managed ? '<span class="case-managed-flag" title="Criado ou editado na tela — o sistema não sobrescreve">editado</span>' : ""}
        <div class="case-actions">
          <button type="button" class="case-icon-btn" data-edit="${c.code}" title="Editar teste" aria-label="Editar">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
          </button>
          <button type="button" class="case-icon-btn danger" data-del-case="${c.code}" title="Excluir teste" aria-label="Excluir">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
        <span class="case-code-mini" title="Código técnico de referência">${esc(c.code)}</span>
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
        <div class="case-meta">Testado por <span class="who">${c.testado_por ? esc(c.testado_por) : "—"}</span><span class="when">${c.testado_por ? " · " + fmtWhen(c.updated_at) : ""}</span></div>
        <div class="reg-row">
          <label class="reg-field">
            <span class="reg-k">Chamado testado</span>
            <input class="reg-chamado" type="text" value="${esc(c.chamado || "")}" placeholder="qual chamado foi testado" autocomplete="off">
          </label>
        </div>
        <div class="obs-row">
          <div class="obs-list">${obsList(c.observations)}</div>
          <div class="obs-add">
            <textarea class="obs-input" rows="1" placeholder="Adicionar observação..."></textarea>
            <button type="button" class="obs-add-btn">Adicionar</button>
          </div>
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
    const flowCases = CASES.filter((c) => caseFlow(c) === currentFlow);
    const emptyEl = $("#flow-empty");
    if (!flowCases.length) {
      $("#cases").innerHTML = "";
      $("#flow-empty-badge").textContent = "Fluxo " + currentFlow;
      emptyEl.hidden = false;
      buildFilters(flowCases);
      updateStats();
      return;
    }
    emptyEl.hidden = true;
    const order = ["Grupo A", "Grupo B", "Grupo C", "Grupo D"];
    const groups = {};
    flowCases.forEach((c) => { (groups[c.grupo] = groups[c.grupo] || []).push(c); });
    // grupos conhecidos primeiro, depois quaisquer grupos novos (criados pelo usuário)
    const ordered = order.filter((g) => groups[g])
      .concat(Object.keys(groups).filter((g) => !order.includes(g)).sort());
    let html = "";
    ordered.forEach((g) => {
      html += `<div class="grp-heading"><span class="badge">${esc(g)}</span><span class="desc">${esc(GRUPO_DESC[g] || "")}</span></div>`;
      html += groups[g].map(caseCard).join("");
    });
    $("#cases").innerHTML = html;
    attachCardHandlers();
    buildFilters(flowCases);
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
  // IMPORTANTE: cada card so pode ter seus listeners anexados UMA vez.
  // attachCardHandlers() roda no load inicial (todos os cards).
  // rerenderCard() (upload/exclusao de print) chama attachOneCardHandlers()
  // so no card que foi substituido — nunca a versao global, senao os
  // listeners se empilham a cada acao e cada clique dispara N vezes
  // (era a causa da duplicacao de prints ao anexar).
  function attachCardHandlers() {
    $$(".case").forEach(attachOneCardHandlers);
  }

  function attachOneCardHandlers(card) {
    const code = card.dataset.code;

    const editBtn = $(".case-icon-btn[data-edit]", card);
    if (editBtn) editBtn.addEventListener("click", () => openCaseModal("edit", code));
    const delBtn = $(".case-icon-btn[data-del-case]", card);
    if (delBtn) delBtn.addEventListener("click", () => deleteCase(code));

    // registro de execução: chamado testado (salva sozinho ao sair do campo)
    const chamadoInput = $(".reg-chamado", card);
    if (chamadoInput) chamadoInput.addEventListener("change", async () => {
      try {
        const updated = await api(`/api/cases/${encodeURIComponent(code)}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chamado: chamadoInput.value.trim() }),
        });
        patchCaseLocal(code, updated);
        toast("Chamado salvo");
      } catch (e) { toast("Erro ao salvar: " + e.message, true); }
    });

    const updateMeta = (updated) => {
      const whoEl = $(".case-meta .who", card);
      const whenEl = $(".case-meta .when", card);
      if (whoEl) whoEl.textContent = updated.testado_por ? updated.testado_por : "—";
      if (whenEl) whenEl.textContent = updated.testado_por ? " · " + fmtWhen(updated.updated_at) : "";
    };

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
          updateMeta(updated);
          updateStats();
          toast(`${code} → ${s}`);
        } catch (e) { toast("Erro ao salvar: " + e.message, true); }
      });
    });

    const obsInput = $(".obs-input", card);
    const obsBtn = $(".obs-add-btn", card);
    const submitObs = async () => {
      const texto = obsInput.value.trim();
      if (!texto) return;
      obsBtn.disabled = true;
      try {
        const updated = await api(`/api/cases/${encodeURIComponent(code)}/observacoes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ texto, autor: testerName() || undefined }),
        });
        patchCaseLocal(code, updated);
        rerenderCard(code);
        toast("Observação adicionada");
      } catch (e) {
        toast("Erro ao salvar observação: " + e.message, true);
      } finally {
        obsBtn.disabled = false;
      }
    };
    obsBtn.addEventListener("click", submitObs);
    obsInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitObs(); }
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

    $$(".shots-grid .shot-thumb", card).forEach((thumb) => {
      const img = $("img", thumb);
      if (!img) return;
      img.addEventListener("click", () => {
        const shotId = parseInt(thumb.dataset.shot, 10);
        const slides = caseShots(code);
        const idx = slides.findIndex((s) => s.id === shotId);
        openCarousel(slides, idx < 0 ? 0 : idx, `Evidências — ${code}`);
      });
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
  }

  function rerenderCard(code) {
    const c = findCase(code);
    const old = document.querySelector(`.case[data-code="${cssEscape(code)}"]`);
    if (!old || !c) return;
    const wrap = document.createElement("div");
    wrap.innerHTML = caseCard(c);
    const fresh = wrap.firstElementChild;
    old.replaceWith(fresh);
    attachOneCardHandlers(fresh);
    applyFilters();
    updatePresentCount();
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
    syncStatTiles();
    updateFiltersActiveCount();
  }
  $("#f-busca").addEventListener("input", applyFilters);

  // filtros recolhíveis + contador de quantos estão ativos (aparece mesmo recolhido)
  function updateFiltersActiveCount() {
    const n = ["grupo", "estagio", "frente", "status"].filter((k) => activeFilters[k]).length;
    const el = $("#filters-active-count");
    if (el) { el.textContent = n; el.hidden = n === 0; }
  }
  const filtersToggle = $("#filters-toggle");
  const filtersBody = $("#filters-body");
  filtersToggle.addEventListener("click", () => {
    const open = filtersBody.hidden;
    filtersBody.hidden = !open;
    filtersToggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

  // ---------------- stats ----------------
  function updateStats() {
    const flowCases = CASES.filter((c) => caseFlow(c) === currentFlow);
    const counts = { "Não testado": 0, "Aprovado": 0, "Reprovado": 0, "Bloqueado": 0, "N/A": 0 };
    flowCases.forEach((c) => { counts[c.status] = (counts[c.status] || 0) + 1; });
    $("#stat-nt").textContent = counts["Não testado"];
    $("#stat-ok").textContent = counts["Aprovado"];
    $("#stat-bad").textContent = counts["Reprovado"];
    $("#stat-warn").textContent = counts["Bloqueado"];
    $("#stat-na").textContent = counts["N/A"];
    updatePresentCount();
  }

  // KPIs clicáveis: cada card de status filtra a lista (clicar de novo limpa).
  // Mantém os chips de Status em sincronia — são duas faces do mesmo filtro.
  function syncStatTiles() {
    $$("#stat-strip .stat").forEach((t) => t.classList.toggle("active", t.dataset.k === activeFilters.status));
  }
  $$("#stat-strip .stat").forEach((tile) => {
    tile.addEventListener("click", () => {
      const k = tile.dataset.k;
      activeFilters.status = activeFilters.status === k ? "" : k;
      $$("#chips-status .chip").forEach((b) => b.classList.toggle("active", b.dataset.val === activeFilters.status));
      applyFilters();
    });
  });

  // ---------------- flow tabs (Fluxo A / B / C) ----------------
  // Hoje todo o conteúdo é do Fluxo C. Fluxo A e B ficam separados como abas
  // "ainda não iniciadas" — quando começarem os testes, os casos ganham um
  // marcador de fluxo (campo `fluxo`) e caem na aba certa; por ora tudo cai em C.
  let currentFlow = "C";
  function caseFlow(c) { return c.fluxo || "C"; }

  function setFlow(flow) {
    currentFlow = flow;
    $$(".flow-tab").forEach((t) => {
      const on = t.dataset.flow === flow;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    activeFilters.grupo = activeFilters.estagio = activeFilters.frente = activeFilters.status = "";
    const busca = $("#f-busca");
    if (busca) busca.value = "";
    render();
    loadActivities();
    if (typeof onFlowChangedForDiagrams === "function") onFlowChangedForDiagrams();
    if (typeof onFlowChangedForSituacoes === "function") onFlowChangedForSituacoes();
  }
  $$(".flow-tab").forEach((t) => t.addEventListener("click", () => setFlow(t.dataset.flow)));

  // ---------------- carrossel de evidências (modo apresentação) ----------------
  const STATUS_CAP = { "Aprovado": "ok", "Reprovado": "bad", "Bloqueado": "warn", "N/A": "na", "Não testado": "nt" };
  const carState = { slides: [], i: 0 };

  function slideOf(c, s) {
    return {
      id: s.id, filename: s.filename, uploaded_by: s.uploaded_by, created_at: s.created_at,
      code: c.code, estagio: c.estagio, estagio_num: c.estagio_num, frente: c.frente, status: c.status,
      chamado: c.chamado,
    };
  }
  function cmpSlide(a, b) {
    const an = a.estagio_num == null ? 999 : a.estagio_num;
    const bn = b.estagio_num == null ? 999 : b.estagio_num;
    if (an !== bn) return an - bn;                     // ordena por estágio (01→12)
    if (a.code !== b.code) return a.code < b.code ? -1 : 1;
    return a.id - b.id;                                 // e por ordem de upload dentro do caso
  }
  function flowShots(flow) {
    const slides = [];
    CASES.filter((c) => caseFlow(c) === flow).forEach((c) => {
      (c.screenshots || []).forEach((s) => slides.push(slideOf(c, s)));
    });
    return slides.sort(cmpSlide);
  }
  function caseShots(code) {
    const c = findCase(code);
    return c ? (c.screenshots || []).map((s) => slideOf(c, s)) : [];
  }

  function openCarousel(slides, startIndex, title) {
    carState.slides = slides;
    carState.i = Math.max(0, Math.min(startIndex || 0, slides.length - 1));
    $("#carousel-title").textContent = title;
    buildTrack();
    renderSlide();
    $("#carousel").hidden = false;
  }
  function closeCarousel() { $("#carousel").hidden = true; }

  function buildTrack() {
    const track = $("#carousel-track");
    track.innerHTML = carState.slides.map((s, i) =>
      `<button type="button" class="track-dot" data-i="${i}" title="${esc(s.estagio)}"><img src="/api/screenshots/${s.id}" alt="" loading="lazy"></button>`
    ).join("");
    $$(".track-dot", track).forEach((d) => d.addEventListener("click", () => { carState.i = parseInt(d.dataset.i, 10); renderSlide(); }));
  }

  function renderSlide() {
    const { slides, i } = carState;
    const img = $("#carousel-img");
    const empty = $("#carousel-empty");
    const prev = $("#carousel-prev"), next = $("#carousel-next");
    if (!slides.length) {
      empty.hidden = false; img.style.display = "none";
      $("#carousel-counter").textContent = "0 / 0";
      $("#carousel-caption").innerHTML = "";
      prev.disabled = next.disabled = true;
      return;
    }
    empty.hidden = true; img.style.display = "";
    const s = slides[i];
    img.src = `/api/screenshots/${s.id}`;
    img.alt = s.filename || "Evidência";
    $("#carousel-counter").textContent = `${i + 1} / ${slides.length}`;
    prev.disabled = i === 0;
    next.disabled = i === slides.length - 1;
    const stCode = STATUS_CAP[s.status] || "nt";
    const regBits = s.chamado ? "Chamado " + esc(s.chamado) : "";
    const metaBits = [
      `<span class="cap-code">${esc(s.code)}</span>`,
      s.uploaded_by ? "enviado por " + esc(s.uploaded_by) : "",
      s.created_at ? fmtWhen(s.created_at) : "",
    ].filter(Boolean).join(" · ");
    $("#carousel-caption").innerHTML =
      `<div class="cap-line">
        <span class="cap-stage">${esc(s.estagio)}</span>
        <span class="cap-tag">${esc(s.frente)}</span>
        <span class="cap-tag cap-status ${stCode}">${esc(s.status)}</span>
      </div>
      ${regBits ? `<div class="cap-reg">${regBits}</div>` : ""}
      <div class="cap-meta">${metaBits}</div>`;
    const dots = $$(".track-dot", $("#carousel-track"));
    dots.forEach((d, di) => d.classList.toggle("active", di === i));
    if (dots[i]) dots[i].scrollIntoView({ inline: "center", block: "nearest" });
  }

  function carNext() { if (carState.i < carState.slides.length - 1) { carState.i++; renderSlide(); } }
  function carPrev() { if (carState.i > 0) { carState.i--; renderSlide(); } }

  $("#carousel-next").addEventListener("click", carNext);
  $("#carousel-prev").addEventListener("click", carPrev);
  $("#carousel-close").addEventListener("click", closeCarousel);
  $("#carousel").addEventListener("click", (e) => { if (e.target.id === "carousel") closeCarousel(); });
  document.addEventListener("keydown", (e) => {
    if ($("#carousel").hidden) return;
    if (e.key === "Escape") closeCarousel();
    else if (e.key === "ArrowRight") carNext();
    else if (e.key === "ArrowLeft") carPrev();
  });

  $("#btn-present").addEventListener("click", () => {
    const slides = flowShots(currentFlow);
    if (!slides.length) { toast("Nenhum print anexado ainda neste fluxo."); return; }
    openCarousel(slides, 0, `Evidências — Fluxo ${currentFlow}`);
  });

  function updatePresentCount() {
    const n = flowShots(currentFlow).length;
    const el = $("#present-count");
    if (el) el.textContent = n === 1 ? "1 print" : `${n} prints`;
    const btn = $("#btn-present");
    if (btn) btn.disabled = n === 0;
  }

  // ---------------- exportar excel ----------------
  // Baixa o fluxo aberto no formato da planilha de acompanhamento (# / Estágio /
  // Problema encontrado / Ajuste solicitado / Status) — o servidor monta o .xlsx.
  $("#btn-export").addEventListener("click", () => {
    const url = `/api/export?fluxo=${encodeURIComponent(currentFlow)}`;
    const a = document.createElement("a");
    a.href = url;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast(`Exportando Fluxo ${currentFlow}...`);
  });

  // ---------------- modal: criar / editar / excluir caso ----------------
  let editingCode = null;
  const modal = $("#case-modal");
  const form = $("#case-form");

  function openCaseModal(mode, code) {
    editingCode = mode === "edit" ? code : null;
    $("#modal-title").textContent = mode === "edit" ? "Editar teste" : "Novo teste";
    const codeEl = $("#modal-code");
    if (mode === "edit") {
      const c = findCase(code);
      if (!c) return;
      codeEl.textContent = c.code; codeEl.hidden = false;
      form.fluxo.value = caseFlow(c);
      form.grupo.value = c.grupo || "";
      form.prioridade.value = c.prioridade || "Média";
      form.estagio.value = c.estagio || "";
      form.frente.value = c.frente || "A definir";
      form.pre_condicao.value = c.pre_condicao || "";
      form.passos.value = c.passos || "";
      form.resultado_esperado.value = c.resultado_esperado || "";
      form.chamado.value = c.chamado || "";
    } else {
      form.reset();
      codeEl.hidden = true;
      form.fluxo.value = currentFlow;   // teste novo entra no fluxo que está aberto
      form.grupo.value = "Grupo C";
      form.prioridade.value = "Média";
      form.frente.value = "A definir";
    }
    modal.hidden = false;
    setTimeout(() => { try { form.estagio.focus(); } catch (e) {} }, 30);
  }
  function closeCaseModal() { modal.hidden = true; editingCode = null; }

  async function submitCaseForm(e) {
    e.preventDefault();
    const payload = {
      fluxo: form.fluxo.value,
      grupo: form.grupo.value.trim() || "Grupo C",
      prioridade: form.prioridade.value,
      estagio: form.estagio.value.trim(),
      frente: form.frente.value,
      pre_condicao: form.pre_condicao.value.trim(),
      passos: form.passos.value.trim(),
      resultado_esperado: form.resultado_esperado.value.trim(),
      chamado: form.chamado.value.trim(),
    };
    if (!payload.estagio) { toast("Informe o estágio.", true); return; }
    if (!payload.resultado_esperado) { toast("Informe o resultado esperado.", true); return; }
    const saveBtn = $("#modal-save");
    saveBtn.disabled = true;
    try {
      if (editingCode) {
        await api(`/api/cases/${encodeURIComponent(editingCode)}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        toast("Teste atualizado");
      } else {
        await api("/api/cases", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        toast("Teste criado");
      }
      const targetFlow = payload.fluxo;
      await loadCases();
      setFlow(targetFlow);   // leva você pro fluxo onde o teste ficou
      closeCaseModal();
    } catch (err) {
      toast("Erro ao salvar: " + err.message, true);
    } finally {
      saveBtn.disabled = false;
    }
  }

  async function deleteCase(code) {
    if (!confirm(`Excluir o teste ${code}? Ele sai da lista (dá pra recriar depois).`)) return;
    try {
      await api(`/api/cases/${encodeURIComponent(code)}`, { method: "DELETE" });
      CASES = CASES.filter((c) => c.code !== code);
      render();
      toast("Teste excluído");
    } catch (err) {
      toast("Erro ao excluir: " + err.message, true);
    }
  }

  form.addEventListener("submit", submitCaseForm);
  $("#modal-close").addEventListener("click", closeCaseModal);
  $("#modal-cancel").addEventListener("click", closeCaseModal);
  modal.addEventListener("click", (e) => { if (e.target.id === "case-modal") closeCaseModal(); });
  $("#btn-add-case").addEventListener("click", () => openCaseModal("create"));
  $("#flow-empty-add").addEventListener("click", () => openCaseModal("create"));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !modal.hidden) closeCaseModal(); });

  // ---------------- pontos para reunião ----------------
  // Painel lateral fixo (aba na borda direita), aberto por cima de qualquer
  // módulo/view — independente de fluxo. Não precisa de caso de teste vinculado.
  let NOTES = [];
  let notesFlowFilter = "";   // "" = todos os fluxos

  async function loadNotes() {
    try {
      NOTES = await api(`/api/notas${notesFlowFilter ? "?fluxo=" + encodeURIComponent(notesFlowFilter) : ""}`);
    } catch (e) {
      NOTES = [];
    }
    updateNotesCount();
    renderNotesList();
  }

  function updateNotesCount() {
    const open = NOTES.filter((n) => !n.resolvido).length;
    const el = $("#pontos-tab-count");
    if (el) { el.textContent = open; el.hidden = open === 0; }
  }

  function noteItem(n) {
    const state = n.resolvido ? "resolvido" : (n.cobrado ? "cobrado" : "pendente");
    return `<div class="note-item ${state}" data-id="${n.id}">
      <div class="note-head">
        <span class="tag note-flow">Fluxo ${esc(n.fluxo)}</span>
        ${n.estagio ? `<span class="tag note-stage">${esc(n.estagio)}</span>` : ""}
        <button type="button" class="note-del" title="Excluir ponto" aria-label="Excluir">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
      <div class="note-text">${esc(n.texto)}</div>
      <div class="note-flags">
        <label class="note-flag">
          <input type="checkbox" class="note-check-cobrado" ${n.cobrado ? "checked" : ""}>
          Já cobramos
        </label>
        <label class="note-flag">
          <input type="checkbox" class="note-check-resolvido" ${n.resolvido ? "checked" : ""}>
          Resolvido
        </label>
      </div>
      <div class="note-meta">${n.autor ? esc(n.autor) + " · " : ""}${fmtWhen(n.created_at)}${n.cobrado ? ` · cobrado ${fmtWhen(n.cobrado_em)}` : ""}${n.resolvido ? ` · resolvido ${fmtWhen(n.resolvido_em)}` : ""}</div>
    </div>`;
  }

  function renderNotesList() {
    const el = $("#notes-list");
    if (!el) return;
    if (!NOTES.length) {
      el.innerHTML = `<div class="notes-empty">Nenhum ponto anotado ainda${notesFlowFilter ? " neste fluxo" : ""}.</div>`;
      return;
    }
    el.innerHTML = NOTES.map(noteItem).join("");
    $$(".note-check-cobrado", el).forEach((chk) => {
      chk.addEventListener("change", () => toggleNote(chk.closest(".note-item").dataset.id, { cobrado: chk.checked }));
    });
    $$(".note-check-resolvido", el).forEach((chk) => {
      chk.addEventListener("change", () => toggleNote(chk.closest(".note-item").dataset.id, { resolvido: chk.checked }));
    });
    $$(".note-del", el).forEach((btn) => {
      btn.addEventListener("click", () => deleteNote(btn.closest(".note-item").dataset.id));
    });
  }

  async function toggleNote(id, patch) {
    try {
      const updated = await api(`/api/notas/${id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
      });
      const idx = NOTES.findIndex((n) => n.id === updated.id);
      if (idx >= 0) NOTES[idx] = updated;
      renderNotesList();
      updateNotesCount();
    } catch (e) { toast("Erro ao atualizar ponto: " + e.message, true); }
  }

  async function deleteNote(id) {
    try {
      await api(`/api/notas/${id}`, { method: "DELETE" });
      NOTES = NOTES.filter((n) => String(n.id) !== String(id));
      renderNotesList();
      updateNotesCount();
    } catch (e) { toast("Erro ao excluir ponto: " + e.message, true); }
  }

  $$("#pontos-chips-flow .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      notesFlowFilter = chip.dataset.flow;
      $$("#pontos-chips-flow .chip").forEach((c) => c.classList.toggle("active", c === chip));
      loadNotes();
    });
  });

  $("#notes-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#notes-input");
    const estagioInput = $("#notes-estagio");
    const flowSelect = $("#notes-add-flow");
    const texto = input.value.trim();
    if (!texto) return;
    try {
      const created = await api("/api/notas", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fluxo: flowSelect.value, texto, autor: testerName() || undefined,
          estagio: estagioInput.value.trim() || undefined,
        }),
      });
      if (!notesFlowFilter || notesFlowFilter === created.fluxo) NOTES.push(created);
      input.value = "";
      estagioInput.value = "";
      renderNotesList();
      updateNotesCount();
    } catch (err) { toast("Erro ao salvar ponto: " + err.message, true); }
  });

  const pontosFab = $("#pontos-fab");
  const pontosPanel = $("#pontos-panel");
  const pontosOverlay = $("#pontos-overlay");

  function openPontosPanel() {
    pontosPanel.hidden = false;
    pontosOverlay.hidden = false;
    pontosFab.setAttribute("aria-expanded", "true");
    pontosFab.classList.add("is-open");
  }
  function closePontosPanel() {
    pontosPanel.hidden = true;
    pontosOverlay.hidden = true;
    pontosFab.setAttribute("aria-expanded", "false");
    pontosFab.classList.remove("is-open");
  }
  pontosFab.addEventListener("click", () => {
    if (pontosPanel.hidden) openPontosPanel(); else closePontosPanel();
  });
  $("#pontos-panel-close").addEventListener("click", closePontosPanel);
  pontosOverlay.addEventListener("click", closePontosPanel);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !pontosPanel.hidden) closePontosPanel(); });

  // ---------------- fluxos (diagramas Mermaid) ----------------
  let currentView = "situacoes";     // "testes" | "fluxos" | "situacoes"
  let DIAGRAMS = [];
  let diagramsLoaded = false;
  const expandedDiagrams = new Set();   // ids dos diagramas abertos (recolhidos por padrão)
  const KIND_LABEL = { atual: "Como está hoje", ideal: "Como deveria funcionar" };
  let mermaidSeq = 0;

  // O Mermaid é carregado como módulo ES (CDN) e sinaliza quando pronto.
  function whenMermaid() {
    if (window.__mermaidReady && window.mermaid) return Promise.resolve(window.mermaid);
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error("Mermaid não carregou (sem conexão?)")), 8000);
      document.addEventListener("mermaid-ready", () => { clearTimeout(t); resolve(window.mermaid); }, { once: true });
    });
  }

  // Renderiza um código Mermaid dentro de um container. Mostra erro amigável se o
  // desenho estiver inválido, sem quebrar o resto da tela.
  async function renderMermaidInto(container, code) {
    const src = (code || "").trim();
    if (!src) { container.innerHTML = `<div class="diagram-preview-empty">Sem diagrama.</div>`; return; }
    let mermaid;
    try { mermaid = await whenMermaid(); }
    catch (e) { container.innerHTML = `<div class="diagram-error">${esc(e.message)}</div>`; return; }
    const id = "mmd-" + (++mermaidSeq);
    try {
      const { svg } = await mermaid.render(id, src);
      container.innerHTML = svg;
    } catch (err) {
      const msg = (err && err.message ? err.message : String(err)).split("\n").slice(0, 6).join("\n");
      container.innerHTML = `<div class="diagram-error">⚠ Erro no diagrama:\n${esc(msg)}</div>`;
    }
  }

  function switchView(view) {
    currentView = view;
    $$(".view-tab").forEach((t) => {
      const on = t.dataset.view === view;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    $("#view-testes").hidden = view !== "testes";
    $("#view-fluxos").hidden = view !== "fluxos";
    $("#view-situacoes").hidden = view !== "situacoes";
    if (view === "fluxos") loadDiagrams();
    if (view === "situacoes") loadSituacoes();
  }

  function onFlowChangedForDiagrams() {
    $("#diagrams-title").textContent = "Fluxos do Fluxo " + currentFlow;
    $("#diagrams-empty-badge").textContent = "Fluxo " + currentFlow;
    if (currentView === "fluxos") renderDiagrams();
  }

  async function loadDiagrams() {
    if (!diagramsLoaded) $("#diagrams-loading").hidden = false;
    try {
      DIAGRAMS = await api("/api/diagramas");
      diagramsLoaded = true;
    } catch (e) {
      $("#diagrams-loading").textContent = "Erro ao carregar diagramas: " + e.message;
      return;
    }
    $("#diagrams-loading").hidden = true;
    renderDiagrams();
  }

  function diagramCard(d) {
    const open = expandedDiagrams.has(d.id);
    return `<article class="diagram kind-${esc(d.kind)} ${open ? "" : "collapsed"}" data-id="${d.id}">
      <div class="diagram-head">
        <button type="button" class="diagram-toggle" aria-label="Abrir/recolher" aria-expanded="${open ? "true" : "false"}">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
        <span class="diagram-kind">${esc(KIND_LABEL[d.kind] || d.kind)}</span>
        <span class="diagram-title">${esc(d.titulo)}</span>
        <span class="diagram-actions">
          <button type="button" class="case-icon-btn diagram-inline-toggle" title="Editar direto no desenho" aria-label="Editar aqui" aria-pressed="false">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
            <span class="inline-toggle-label">Editar aqui</span>
          </button>
          <button type="button" class="case-icon-btn diagram-edit" title="Editor completo (título, tipo, código)" aria-label="Editor completo">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button type="button" class="case-icon-btn danger diagram-del" title="Excluir diagrama" aria-label="Excluir">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </span>
      </div>
      <div class="diagram-body">
        ${d.descricao ? `<div class="diagram-desc">${esc(d.descricao)}</div>` : ""}
        <div class="inline-toolbar" data-toolbar="${d.id}" hidden>
          <span class="inline-tb-hint">Renomear: clique na caixa · Ligar: <b>arraste o +</b> · seta: clique traceja, <b>Aa</b> rotula (Sim/Não), <b>⇄</b>/<b>×</b> inverte/exclui · <b>Delete</b> apaga o que está sob o mouse</span>
          <span class="inline-tb-spacer"></span>
          <button type="button" class="inline-undo" title="Desfazer (Ctrl+Z)" disabled>↶ Desfazer</button>
          <div class="inline-dir" role="group" aria-label="Sentido do fluxo">
            <button type="button" class="inline-dir-btn" data-dir="TD" title="Vertical">↓</button>
            <button type="button" class="inline-dir-btn" data-dir="LR" title="Horizontal">→</button>
          </div>
          <div class="inline-palette" role="group" aria-label="Adicionar caixa">
            <span class="inline-palette-label">Adicionar:</span>
            <button type="button" class="inline-add-node palette-btn" title="Etapa — caixa retangular do fluxo">
              <svg viewBox="0 0 34 20" width="30" height="18" aria-hidden="true"><rect x="2" y="4" width="30" height="12" rx="2.5" fill="rgba(0,84,236,.10)" stroke="#0054ec" stroke-width="1.6"/></svg>
              <span>Etapa</span>
            </button>
            <button type="button" class="inline-add-botao palette-btn" title="Botão — ação/botão dentro do sistema">
              <svg viewBox="0 0 34 20" width="30" height="18" aria-hidden="true"><rect x="2" y="4" width="30" height="12" rx="4.5" fill="#e0f2fe" stroke="#0284c7" stroke-width="1.6"/></svg>
              <span>Botão</span>
            </button>
            <button type="button" class="inline-add-decision palette-btn" title="Decisão — losango com saídas Sim / Não">
              <svg viewBox="0 0 34 20" width="30" height="18" aria-hidden="true"><polygon points="17,2 32,10 17,18 2,10" fill="rgba(150,10,156,.10)" stroke="#960a9c" stroke-width="1.6"/></svg>
              <span>Decisão</span>
            </button>
            <button type="button" class="inline-add-notif palette-btn" title="Notificação — aviso (push / WhatsApp)">
              <svg viewBox="0 0 34 20" width="30" height="18" aria-hidden="true"><rect x="2" y="4" width="30" height="12" rx="6" fill="rgba(245,158,11,.14)" stroke="#f59e0b" stroke-width="1.6"/></svg>
              <span>🔔 Notificação</span>
            </button>
          </div>
          <span class="inline-save-state" aria-live="polite"></span>
          <button type="button" class="inline-done">Concluir</button>
        </div>
        <div class="diagram-canvas" data-canvas="${d.id}"><div class="diagram-preview-empty">Renderizando…</div></div>
        <div class="diagram-meta-foot">${d.atualizado_por ? `Atualizado por <span class="who">${esc(d.atualizado_por)}</span> · ` : ""}${fmtWhen(d.updated_at)}${d.seeded ? " · <span class=\"who\">modelo inicial</span>" : ""}</div>
      </div>
    </article>`;
  }

  // renderiza o Mermaid de um card só quando ele está aberto (lazy)
  function renderDiagramCanvas(d, wrap) {
    const canvas = (wrap || document).querySelector(`.diagram-canvas[data-canvas="${d.id}"]`);
    if (canvas && !canvas.dataset.rendered) {
      canvas.dataset.rendered = "1";
      renderMermaidInto(canvas, d.mermaid);
    }
  }

  function renderDiagrams() {
    const list = DIAGRAMS.filter((d) => (d.fluxo || "C") === currentFlow)
      .sort((a, b) => (a.kind < b.kind ? -1 : a.kind > b.kind ? 1 : (a.ordem || 0) - (b.ordem || 0)));
    // cancela edições inline pendentes antes de recriar os cards
    inlineState.forEach((st) => { if (st.saveTimer) clearTimeout(st.saveTimer); });
    inlineState.clear();
    const emptyEl = $("#diagrams-empty");
    const wrap = $("#diagrams");
    if (!list.length) {
      wrap.innerHTML = "";
      emptyEl.hidden = false;
      return;
    }
    emptyEl.hidden = true;
    wrap.innerHTML = list.map(diagramCard).join("");
    // só desenha os que estão abertos
    list.forEach((d) => { if (expandedDiagrams.has(d.id)) renderDiagramCanvas(d, wrap); });
    // abrir/recolher pelo cabeçalho (menos os botões de ação)
    $$(".diagram", wrap).forEach((art) => {
      const id = Number(art.dataset.id);
      const d = list.find((x) => x.id === id);
      art.querySelector(".diagram-head").addEventListener("click", (ev) => {
        if (ev.target.closest(".diagram-actions")) return;
        const nowOpen = art.classList.toggle("collapsed") === false;
        art.querySelector(".diagram-toggle").setAttribute("aria-expanded", nowOpen ? "true" : "false");
        if (nowOpen) { expandedDiagrams.add(id); if (d) renderDiagramCanvas(d, wrap); }
        else { expandedDiagrams.delete(id); if (art.classList.contains("editing")) exitInlineEdit(art); }
      });
    });
    $$(".diagram-inline-toggle", wrap).forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const art = btn.closest(".diagram");
        const id = Number(art.dataset.id);
        const d = DIAGRAMS.find((x) => x.id === id);
        if (!d) return;
        // abrir o card se estiver recolhido antes de editar
        if (art.classList.contains("collapsed")) {
          art.classList.remove("collapsed");
          art.querySelector(".diagram-toggle").setAttribute("aria-expanded", "true");
          expandedDiagrams.add(id);
        }
        if (art.classList.contains("editing")) exitInlineEdit(art);
        else enterInlineEdit(art, d);
      });
    });
    $$(".diagram-edit", wrap).forEach((btn) => {
      btn.addEventListener("click", (ev) => { ev.stopPropagation(); openDiagramModal("edit", btn.closest(".diagram").dataset.id); });
    });
    $$(".diagram-del", wrap).forEach((btn) => {
      btn.addEventListener("click", (ev) => { ev.stopPropagation(); deleteDiagram(btn.closest(".diagram").dataset.id); });
    });
  }

  // ---- editor modal (builder por formulário) ----
  let editingDiagramId = null;
  const diagramModal = $("#diagram-modal");
  const diagramForm = $("#diagram-form");
  const diagramSource = $("#diagram-source");
  let previewTimer = null;
  let syncingCode = false;   // evita loop builder <-> código
  let manualCode = false;    // usuário editou o código à mão (modo avançado)
  // estado do builder: { dir, nodes:[{id,label,shape}], edges:[{id,from,to,label,dotted}] }
  let builder = { dir: "TD", nodes: [], edges: [], nSeq: 0, eSeq: 0 };

  function newNodeId(state) {
    const s = state || builder;
    let id;
    do { id = "n" + (++s.nSeq); } while (s.nodes.some((n) => n.id === id));
    return id;
  }

  function newEdgeId(state) {
    const s = state || builder;
    return "e" + (++s.eSeq);
  }

  // --- gerar código Mermaid a partir do estado ---
  function cleanLabel(s) { return (s || "").replace(/["|]/g, " ").replace(/\s+/g, " ").trim(); }
  // destinatários possíveis de uma notificação e a cor de cada um
  const NOTIF_RECIPIENTS = ["Técnico", "Operador", "Cliente", "Todos"];
  // frase natural mostrada na caixa por destinatário
  const NOTIF_PHRASE = {
    "Técnico": "Notifica o técnico", "Operador": "Notifica o operador",
    "Cliente": "Notifica o cliente", "Todos": "Notifica a todos",
  };
  const NOTIF_CLASS = { "Técnico": "notifTec", "Operador": "notifOpr", "Cliente": "notifCli" };
  const NOTIF_CLASSDEF = {
    notif:    "classDef notif fill:#fff7e6,stroke:#f59e0b,stroke-width:1.5px,color:#7c4a03;",
    notifTec: "classDef notifTec fill:#e8f0ff,stroke:#0054ec,stroke-width:1.5px,color:#0b2e75;",
    notifOpr: "classDef notifOpr fill:#f3e8ff,stroke:#9333ea,stroke-width:1.5px,color:#5b1699;",
    notifCli: "classDef notifCli fill:#e7f8ef,stroke:#0d9d6c,stroke-width:1.5px,color:#075e40;",
  };

  function generateMermaid(s) {
    const lines = ["flowchart " + (s.dir || "TD")];
    s.nodes.forEach((n) => {
      const label = cleanLabel(n.label) || n.id;
      if (n.shape === "decision") lines.push(`    ${n.id}{"${label}"}`);
      else if (n.shape === "botao") lines.push(`    ${n.id}("${label}")`);
      else if (n.shape === "notif") {
        const phrase = NOTIF_PHRASE[n.to];
        const msg = cleanLabel(n.label);
        let inner;
        if (phrase) inner = msg ? `🔔 ${phrase}: ${msg}` : `🔔 ${phrase}`;
        else inner = `🔔 ${msg || "Notificação"}`;
        lines.push(`    ${n.id}(["${inner}"])`);
      } else lines.push(`    ${n.id}["${label}"]`);
    });
    s.edges.forEach((e) => {
      if (!e.from || !e.to) return;
      const lbl = cleanLabel(e.label);
      if (e.dotted) lines.push(lbl ? `    ${e.from} -. ${lbl} .-> ${e.to}` : `    ${e.from} -.-> ${e.to}`);
      else lines.push(lbl ? `    ${e.from} -->|${lbl}| ${e.to}` : `    ${e.from} --> ${e.to}`);
    });
    // notificações ganham cor por destinatário (âmbar quando sem destinatário)
    const byClass = {};
    s.nodes.filter((n) => n.shape === "notif").forEach((n) => {
      const cls = NOTIF_CLASS[n.to] || "notif";
      (byClass[cls] = byClass[cls] || []).push(n.id);
    });
    Object.keys(byClass).forEach((cls) => {
      lines.push("    " + NOTIF_CLASSDEF[cls]);
      lines.push("    class " + byClass[cls].join(",") + " " + cls + ";");
    });
    // botões do sistema ganham cor própria (ciano) pra se distinguir das etapas
    const botaoIds = s.nodes.filter((n) => n.shape === "botao").map((n) => n.id);
    if (botaoIds.length) {
      lines.push("    classDef botao fill:#e0f2fe,stroke:#0284c7,stroke-width:1.5px,color:#075985;");
      lines.push("    class " + botaoIds.join(",") + " botao;");
    }
    return lines.join("\n");
  }

  // --- interpretar código Mermaid simples de volta pro estado (best-effort) ---
  function parseMermaid(code) {
    const s = { dir: "TD", nodes: [], edges: [], nSeq: 0, eSeq: 0 };
    const map = new Map();
    const ensure = (id) => {
      if (!map.has(id)) { const n = { id, label: id, shape: "step" }; map.set(id, n); s.nodes.push(n); }
      return map.get(id);
    };
    // extrai definições de nó (inclusive inline numa aresta, ex.: A[x] --> B[y]),
    // registra rótulo/forma e devolve a linha só com os ids (ex.: A --> B).
    // ordem importa: o formato estádio ([...]) precisa sair antes de [...],
    // senão o colchete interno seria lido como uma etapa comum.
    const extractNodes = (line) => {
      line = line.replace(/([A-Za-z0-9_]+)\(\[\s*"?(.*?)"?\s*\]\)/g, (full, id, label) => {
        const n = ensure(id); n.shape = "notif";
        const txt = label.replace(/^🔔\s*/, "").trim();
        n.to = ""; n.label = txt;
        for (const k of NOTIF_RECIPIENTS) {
          const ph = NOTIF_PHRASE[k];
          if (txt === ph) { n.to = k; n.label = ""; break; }
          if (txt.startsWith(ph + ": ")) { n.to = k; n.label = txt.slice(ph.length + 2); break; }
        }
        if (n.label === "Notificação") n.label = "";
        return id;
      });
      // botão: (...) — precisa vir depois do estádio ([...]) e antes de [...],
      // senão o parêntese externo do estádio seria lido como botão
      line = line.replace(/([A-Za-z0-9_]+)\(\s*"?(.*?)"?\s*\)/g, (full, id, label) => {
        const n = ensure(id); n.shape = "botao"; n.label = label; return id;
      });
      line = line.replace(/([A-Za-z0-9_]+)\{\s*"?(.*?)"?\s*\}/g, (full, id, label) => {
        const n = ensure(id); n.shape = "decision"; n.label = label; return id;
      });
      line = line.replace(/([A-Za-z0-9_]+)\[\s*"?(.*?)"?\s*\]/g, (full, id, label) => {
        const n = ensure(id); n.shape = "step"; n.label = label; return id;
      });
      return line;
    };
    (code || "").split("\n").forEach((raw) => {
      let line = raw.trim();
      if (!line) return;
      let m;
      if ((m = line.match(/^(?:flowchart|graph)\s+(TD|TB|LR|RL|BT)/i))) {
        s.dir = m[1].toUpperCase() === "TB" ? "TD" : m[1].toUpperCase();
        return;
      }
      line = extractNodes(line);   // nós (inline ou soltos) já registrados; sobra "A --> B"
      // arestas (checar variações com rótulo antes da simples)
      if ((m = line.match(/^(\w+)\s*-\.\s*(.+?)\s*\.->\s*(\w+)/))) { ensure(m[1]); ensure(m[3]); s.edges.push({ id: "e" + (++s.eSeq), from: m[1], to: m[3], label: m[2], dotted: true }); return; }
      if ((m = line.match(/^(\w+)\s*-\.->\s*(\w+)/))) { ensure(m[1]); ensure(m[2]); s.edges.push({ id: "e" + (++s.eSeq), from: m[1], to: m[2], label: "", dotted: true }); return; }
      if ((m = line.match(/^(\w+)\s*-->\s*\|([^|]*)\|\s*(\w+)/))) { ensure(m[1]); ensure(m[3]); s.edges.push({ id: "e" + (++s.eSeq), from: m[1], to: m[3], label: m[2], dotted: false }); return; }
      if ((m = line.match(/^(\w+)\s*--\s*(.+?)\s*-->\s*(\w+)/))) { ensure(m[1]); ensure(m[3]); s.edges.push({ id: "e" + (++s.eSeq), from: m[1], to: m[3], label: m[2], dotted: false }); return; }
      if ((m = line.match(/^(\w+)\s*-->\s*(\w+)/))) { ensure(m[1]); ensure(m[2]); s.edges.push({ id: "e" + (++s.eSeq), from: m[1], to: m[2], label: "", dotted: false }); return; }
    });
    // nSeq alto o suficiente pra novos ids não colidirem
    s.nodes.forEach((n) => { const mm = /^n(\d+)$/.exec(n.id); if (mm) s.nSeq = Math.max(s.nSeq, +mm[1]); });
    return s;
  }

  // --- opções de <select> das etapas (usadas nas ligações) ---
  function nodeOptions(selected) {
    if (!builder.nodes.length) return `<option value="">— sem etapas —</option>`;
    return builder.nodes.map((n, i) => {
      const txt = `${i + 1}. ${cleanLabel(n.label) || n.id}`;
      return `<option value="${n.id}" ${n.id === selected ? "selected" : ""}>${esc(txt)}</option>`;
    }).join("");
  }

  function renderNodes() {
    const el = $("#nodes-list");
    if (!builder.nodes.length) { el.innerHTML = `<div class="builder-empty">Nenhuma etapa ainda. Clique em “+ Etapa”.</div>`; return; }
    el.innerHTML = builder.nodes.map((n, i) => `
      <div class="builder-row ${n.shape === "decision" ? "is-decision" : ""} ${n.shape === "notif" ? "is-notif" : ""}" data-id="${n.id}">
        <span class="b-num">${i + 1}</span>
        <input type="text" class="b-label" value="${esc(n.label)}" placeholder="texto da etapa">
        <select class="b-shape">
          <option value="step" ${n.shape === "step" ? "selected" : ""}>Etapa</option>
          <option value="botao" ${n.shape === "botao" ? "selected" : ""}>Botão</option>
          <option value="decision" ${n.shape === "decision" ? "selected" : ""}>Decisão</option>
          <option value="notif" ${n.shape === "notif" ? "selected" : ""}>Notificação</option>
        </select>
        <select class="b-recipient" title="Destinatário da notificação">
          <option value="" ${!n.to ? "selected" : ""}>— destinatário —</option>
          ${NOTIF_RECIPIENTS.map((r) => `<option value="${r}" ${n.to === r ? "selected" : ""}>${r}</option>`).join("")}
        </select>
        <button type="button" class="builder-del" title="Remover etapa" aria-label="Remover">×</button>
      </div>`).join("");
    $$(".builder-row", el).forEach((row) => {
      const id = row.dataset.id;
      const node = builder.nodes.find((n) => n.id === id);
      row.querySelector(".b-label").addEventListener("input", (ev) => { node.label = ev.target.value; scheduleSync(); });
      row.querySelector(".b-label").addEventListener("change", () => renderEdges());
      row.querySelector(".b-shape").addEventListener("change", (ev) => {
        node.shape = ev.target.value;
        row.classList.toggle("is-decision", ev.target.value === "decision");
        row.classList.toggle("is-notif", ev.target.value === "notif");
        scheduleSync();
      });
      row.querySelector(".b-recipient").addEventListener("change", (ev) => { node.to = ev.target.value; scheduleSync(); });
      row.querySelector(".builder-del").addEventListener("click", () => {
        builder.nodes = builder.nodes.filter((n) => n.id !== id);
        builder.edges = builder.edges.filter((e) => e.from !== id && e.to !== id);
        renderNodes(); renderEdges(); scheduleSync();
      });
    });
  }

  function renderEdges() {
    const el = $("#edges-list");
    if (!builder.edges.length) { el.innerHTML = `<div class="builder-empty">Nenhuma ligação ainda. Clique em “+ Ligação”.</div>`; return; }
    el.innerHTML = builder.edges.map((e) => `
      <div class="builder-row" data-eid="${e.id}">
        <select class="b-from">${nodeOptions(e.from)}</select>
        <span class="b-arrow">→</span>
        <select class="b-to">${nodeOptions(e.to)}</select>
        <input type="text" class="b-edge-label" value="${esc(e.label || "")}" placeholder="rótulo (ex.: Sim)">
        <label class="b-dotted"><input type="checkbox" ${e.dotted ? "checked" : ""}> tracejada</label>
        <button type="button" class="builder-del" title="Remover ligação" aria-label="Remover">×</button>
      </div>`).join("");
    $$(".builder-row", el).forEach((row) => {
      const eid = row.dataset.eid;
      const edge = builder.edges.find((x) => x.id === eid);
      row.querySelector(".b-from").addEventListener("change", (ev) => { edge.from = ev.target.value; scheduleSync(); });
      row.querySelector(".b-to").addEventListener("change", (ev) => { edge.to = ev.target.value; scheduleSync(); });
      row.querySelector(".b-edge-label").addEventListener("input", (ev) => { edge.label = ev.target.value; scheduleSync(); });
      row.querySelector(".b-dotted input").addEventListener("change", (ev) => { edge.dotted = ev.target.checked; scheduleSync(); });
      row.querySelector(".builder-del").addEventListener("click", () => {
        builder.edges = builder.edges.filter((x) => x.id !== eid);
        renderEdges(); scheduleSync();
      });
    });
  }

  // gera o código a partir do builder, joga no textarea avançado e atualiza o preview
  function scheduleSync() {
    manualCode = false;
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => {
      const code = generateMermaid(builder);
      syncingCode = true;
      diagramSource.value = code;
      syncingCode = false;
      renderPreview(code);
    }, 300);
  }

  function setBuilderState(state) {
    builder = state;
    const dirInput = diagramForm.querySelector(`input[name="builder-dir"][value="${builder.dir}"]`) ||
                     diagramForm.querySelector('input[name="builder-dir"][value="TD"]');
    if (dirInput) dirInput.checked = true;
    renderNodes(); renderEdges();
    const code = generateMermaid(builder);
    syncingCode = true; diagramSource.value = code; syncingCode = false;
    renderPreview(code);
  }

  function starterState() {
    return {
      dir: "TD", nSeq: 2, eSeq: 1,
      nodes: [{ id: "n1", label: "Início", shape: "step" }, { id: "n2", label: "Fim", shape: "step" }],
      edges: [{ id: "e1", from: "n1", to: "n2", label: "", dotted: false }],
    };
  }

  function openDiagramModal(mode, id) {
    editingDiagramId = mode === "edit" ? Number(id) : null;
    $("#diagram-modal-title").textContent = mode === "edit" ? "Editar diagrama" : "Novo diagrama";
    $("#diagram-flow-label").textContent = "Fluxo " + currentFlow;
    let state;
    if (mode === "edit") {
      const d = DIAGRAMS.find((x) => x.id === editingDiagramId);
      if (!d) return;
      diagramForm.titulo.value = d.titulo || "";
      diagramForm.kind.value = d.kind || "atual";
      diagramForm.descricao.value = d.descricao || "";
      state = parseMermaid(d.mermaid || "");
      if (!state.nodes.length) { state = starterState(); diagramSource.value = d.mermaid || ""; }
    } else {
      diagramForm.reset();
      diagramForm.kind.value = "atual";
      state = starterState();
    }
    const adv = $(".builder-advanced"); if (adv) adv.open = false;
    closeNodePopover();
    setBuilderState(state);
    diagramModal.hidden = false;
    setTimeout(() => { try { diagramForm.titulo.focus(); } catch (e) {} }, 30);
  }
  function closeDiagramModal() { diagramModal.hidden = true; editingDiagramId = null; closeNodePopover(); }

  // ---- clique-para-editar direto na pré-visualização ----
  const nodePop = $("#node-popover");
  let popNodeId = null;
  let pendingSelectId = null;   // etapa a selecionar no popover após o próximo render

  // renderiza o preview e (re)liga os cliques nas caixas
  function renderPreview(code) {
    renderMermaidInto($("#diagram-preview"), code).then(() => {
      attachPreviewEditing();
      if (pendingSelectId) {
        const g = findNodeG(pendingSelectId);
        if (g) openNodePopover(pendingSelectId, g);
        pendingSelectId = null;
      }
    });
  }

  function nodeIdFromG(g) {
    const m = /-flowchart-([A-Za-z0-9_]+)-\d+$/.exec(g.id || "");
    return m ? m[1] : null;
  }
  function findNodeG(id) {
    return $$("#diagram-preview svg g.node").find((g) => nodeIdFromG(g) === id) || null;
  }
  function attachPreviewEditing() {
    const svg = $("#diagram-preview svg");
    if (!svg) return;
    $$("g.node", svg).forEach((g) => {
      const id = nodeIdFromG(g);
      if (!id) return;
      g.addEventListener("click", (ev) => { ev.stopPropagation(); openNodePopover(id, g); });
    });
  }

  function openNodePopover(id, g) {
    const node = builder.nodes.find((n) => n.id === id);
    if (!node) return;
    popNodeId = id;
    $("#mm-pop-label").value = node.label || "";
    $("#mm-pop-shape").value = node.shape || "step";
    nodePop.hidden = false;
    const col = $(".diagram-preview-col");
    const cr = col.getBoundingClientRect();
    const gr = g.getBoundingClientRect();
    let left = gr.left - cr.left + gr.width / 2 - nodePop.offsetWidth / 2;
    let top = gr.bottom - cr.top + 8;
    left = Math.max(6, Math.min(left, col.clientWidth - nodePop.offsetWidth - 6));
    top = Math.max(6, Math.min(top, col.clientHeight - nodePop.offsetHeight - 6));
    nodePop.style.left = left + "px";
    nodePop.style.top = top + "px";
    setTimeout(() => { try { const el = $("#mm-pop-label"); el.focus(); el.select(); } catch (e) {} }, 20);
  }
  function closeNodePopover() { if (nodePop) { nodePop.hidden = true; } popNodeId = null; }

  async function submitDiagramForm(e) {
    e.preventDefault();
    const payload = {
      fluxo: currentFlow,
      kind: diagramForm.kind.value,
      titulo: diagramForm.titulo.value.trim(),
      descricao: diagramForm.descricao.value.trim(),
      mermaid: (manualCode ? diagramSource.value : generateMermaid(builder)).trim(),
      atualizado_por: testerName() || undefined,
    };
    if (!payload.titulo) { toast("Informe o título.", true); return; }
    if (!payload.mermaid) { toast("Informe o diagrama.", true); return; }
    const saveBtn = $("#diagram-save");
    saveBtn.disabled = true;
    try {
      if (editingDiagramId) {
        await api(`/api/diagramas/${editingDiagramId}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        expandedDiagrams.add(editingDiagramId);   // deixa aberto pra ver o resultado
        toast("Diagrama atualizado");
      } else {
        const created = await api("/api/diagramas", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        if (created && created.id) expandedDiagrams.add(created.id);
        toast("Diagrama criado");
      }
      await loadDiagrams();
      closeDiagramModal();
    } catch (err) {
      toast("Erro ao salvar: " + err.message, true);
    } finally {
      saveBtn.disabled = false;
    }
  }

  async function deleteDiagram(id) {
    if (!confirm("Excluir este diagrama?")) return;
    try {
      await api(`/api/diagramas/${id}`, { method: "DELETE" });
      DIAGRAMS = DIAGRAMS.filter((d) => String(d.id) !== String(id));
      renderDiagrams();
      toast("Diagrama excluído");
    } catch (err) {
      toast("Erro ao excluir: " + err.message, true);
    }
  }

  // ---------------- edição inline direto no card (sem modal) ----------------
  // Cada card guarda seu próprio estado de builder enquanto está em edição.
  // As alterações regeram o Mermaid, redesenham o SVG e salvam sozinhas (debounce).
  const inlineState = new Map();   // id do diagrama -> { d, state, saveTimer, renaming }

  function enterInlineEdit(art, d) {
    // sai de qualquer outro card em edição (um de cada vez, evita confusão)
    $$(".diagram.editing").forEach((other) => { if (other !== art) exitInlineEdit(other); });
    const state = parseMermaid(d.mermaid || "");
    if (!state.nodes.length) { toast("Esse desenho é complexo demais pra editar aqui — use o editor completo.", true); return; }
    const st = { d, state, saveTimer: null, dirty: false, history: [cloneState(state)], hoverNodeId: null, hoverEdgeId: null };
    inlineState.set(d.id, st);
    art.classList.add("editing");
    const tb = art.querySelector(".inline-toolbar");
    if (tb) { tb.hidden = false; wireInlineToolbar(art, st); }
    const toggle = art.querySelector(".diagram-inline-toggle");
    if (toggle) { toggle.setAttribute("aria-pressed", "true"); toggle.classList.add("active"); const lbl = toggle.querySelector(".inline-toggle-label"); if (lbl) lbl.textContent = "Editando"; }
    syncInlineDirButtons(art, st);
    renderInlineCanvas(art, st);
  }

  function exitInlineEdit(art) {
    const id = Number(art.dataset.id);
    const st = inlineState.get(id);
    if (st && st.saveTimer) { clearTimeout(st.saveTimer); saveInline(art, st, true); }
    inlineState.delete(id);
    art.classList.remove("editing");
    const tb = art.querySelector(".inline-toolbar");
    if (tb) tb.hidden = true;
    const toggle = art.querySelector(".diagram-inline-toggle");
    if (toggle) { toggle.setAttribute("aria-pressed", "false"); toggle.classList.remove("active"); const lbl = toggle.querySelector(".inline-toggle-label"); if (lbl) lbl.textContent = "Editar aqui"; }
    // volta ao desenho estático limpo
    const canvas = art.querySelector(".diagram-canvas");
    const d = DIAGRAMS.find((x) => x.id === id);
    if (canvas && d) { canvas.dataset.rendered = "1"; renderMermaidInto(canvas, d.mermaid); }
  }

  function wireInlineToolbar(art, st) {
    const tb = art.querySelector(".inline-toolbar");
    if (!tb || tb.dataset.wired) return;
    tb.dataset.wired = "1";
    tb.addEventListener("click", (e) => e.stopPropagation());
    $$(".inline-dir-btn", tb).forEach((b) => b.addEventListener("click", () => {
      st.state.dir = b.dataset.dir;
      syncInlineDirButtons(art, st);
      commitInline(art, st);
    }));
    const addBtn = tb.querySelector(".inline-add-node");
    if (addBtn) addBtn.addEventListener("click", () => {
      const id = newNodeId(st.state);
      st.state.nodes.push({ id, label: "Nova etapa", shape: "step" });
      commitInline(art, st, id);
    });
    const addBotao = tb.querySelector(".inline-add-botao");
    if (addBotao) addBotao.addEventListener("click", () => {
      const id = newNodeId(st.state);
      st.state.nodes.push({ id, label: "Botão", shape: "botao" });
      commitInline(art, st, id);
    });
    const addDecision = tb.querySelector(".inline-add-decision");
    if (addDecision) addDecision.addEventListener("click", () => {
      const id = newNodeId(st.state);
      st.state.nodes.push({ id, label: "Decisão?", shape: "decision" });
      commitInline(art, st, id);
    });
    const addNotif = tb.querySelector(".inline-add-notif");
    if (addNotif) addNotif.addEventListener("click", () => {
      const id = newNodeId(st.state);
      // já entra endereçada ao técnico; o 👤 troca o destinatário
      st.state.nodes.push({ id, label: "", shape: "notif", to: "Técnico" });
      commitInline(art, st);
    });
    const undoBtn = tb.querySelector(".inline-undo");
    if (undoBtn) undoBtn.addEventListener("click", () => undoInline(art, st));
    const doneBtn = tb.querySelector(".inline-done");
    if (doneBtn) doneBtn.addEventListener("click", () => exitInlineEdit(art));
  }

  // ---- histórico (desfazer) ----
  const cloneState = (s) => JSON.parse(JSON.stringify(s));
  function pushHistory(st) {
    if (st._restoring) return;
    st.history = st.history || [];
    st.history.push(cloneState(st.state));
    if (st.history.length > 60) st.history.shift();
  }
  function updateUndoBtn(art, st) {
    const b = art.querySelector(".inline-undo");
    if (b) b.disabled = !st.history || st.history.length < 2;
  }
  function undoInline(art, st) {
    if (!st.history || st.history.length < 2) { toast("Nada pra desfazer"); return; }
    st.history.pop();                                   // descarta o estado atual
    st._restoring = true;
    st.state = cloneState(st.history[st.history.length - 1]);
    st._restoring = false;
    st.dirty = true;
    renderInlineCanvas(art, st);
    scheduleInlineSave(art, st);
    updateUndoBtn(art, st);
    toast("Desfeito");
  }

  function syncInlineDirButtons(art, st) {
    $$(".inline-dir-btn", art).forEach((b) => b.classList.toggle("active", b.dataset.dir === st.state.dir));
  }

  // regenera código, redesenha e agenda salvamento. focusNodeId: renomeia essa etapa após desenhar.
  function commitInline(art, st, focusNodeId) {
    st.dirty = true;
    pushHistory(st);
    updateUndoBtn(art, st);
    renderInlineCanvas(art, st, focusNodeId);
    scheduleInlineSave(art, st);
  }

  function scheduleInlineSave(art, st) {
    setSaveState(art, "saving");
    if (st.saveTimer) clearTimeout(st.saveTimer);
    st.saveTimer = setTimeout(() => saveInline(art, st), 650);
  }

  async function saveInline(art, st, silent) {
    st.saveTimer = null;
    const mermaid = generateMermaid(st.state).trim();
    if (!mermaid) return;
    try {
      const updated = await api(`/api/diagramas/${st.d.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mermaid, atualizado_por: testerName() || undefined }),
      });
      st.d.mermaid = updated.mermaid;
      st.d.updated_at = updated.updated_at;
      st.d.atualizado_por = updated.atualizado_por;
      st.d.seeded = updated.seeded;
      const idx = DIAGRAMS.findIndex((x) => x.id === updated.id);
      if (idx >= 0) DIAGRAMS[idx] = Object.assign(DIAGRAMS[idx], { mermaid: updated.mermaid, updated_at: updated.updated_at, atualizado_por: updated.atualizado_por, seeded: updated.seeded });
      const foot = art.querySelector(".diagram-meta-foot");
      if (foot) foot.innerHTML = `${updated.atualizado_por ? `Atualizado por <span class="who">${esc(updated.atualizado_por)}</span> · ` : ""}${fmtWhen(updated.updated_at)}`;
      st.dirty = false;
      if (!silent) setSaveState(art, "saved");
    } catch (e) {
      setSaveState(art, "error");
      if (!silent) toast("Erro ao salvar: " + e.message, true);
    }
  }

  function setSaveState(art, s) {
    const el = art.querySelector(".inline-save-state");
    if (!el) return;
    el.className = "inline-save-state " + s;
    el.textContent = s === "saving" ? "salvando…" : s === "saved" ? "salvo ✓" : s === "error" ? "erro ao salvar" : "";
    if (s === "saved") { clearTimeout(setSaveState._t); setSaveState._t = setTimeout(() => { if (el.textContent === "salvo ✓") el.textContent = ""; }, 1600); }
  }

  // desenha o SVG editável e (re)constrói a camada de affordances por cima
  function renderInlineCanvas(art, st, focusNodeId) {
    const canvas = art.querySelector(".diagram-canvas");
    if (!canvas) return;
    canvas.dataset.rendered = "1";
    const code = generateMermaid(st.state);
    renderMermaidInto(canvas, code).then(() => {
      buildInlineAffordances(art, st);
      if (focusNodeId) startRename(art, st, focusNodeId);
    });
  }

  function inlineNodeId(g) {
    const m = /-flowchart-([A-Za-z0-9_]+)-\d+$/.exec(g.id || "");
    return m ? m[1] : null;
  }

  function buildInlineAffordances(art, st) {
    const canvas = art.querySelector(".diagram-canvas");
    const svg = canvas.querySelector("svg");
    if (!svg) return;
    canvas.classList.add("inline-canvas");
    // camada de overlay cobrindo exatamente o SVG
    let fx = canvas.querySelector(".inline-fx");
    if (fx) fx.remove();
    fx = document.createElement("div");
    fx.className = "inline-fx";
    canvas.appendChild(fx);
    fx.style.left = svg.offsetLeft + "px";
    fx.style.top = svg.offsetTop + "px";
    fx.style.width = svg.offsetWidth + "px";
    fx.style.height = svg.offsetHeight + "px";
    const fxRect = fx.getBoundingClientRect();

    // ---- nós: renomear no clique + botões +, forma e excluir ----
    $$("g.node", svg).forEach((g) => {
      const nid = inlineNodeId(g);
      const node = st.state.nodes.find((n) => n.id === nid);
      if (!node) return;
      g.classList.add("inline-node");
      g.addEventListener("click", (ev) => {
        if (ev.target.closest && ev.target.closest(".inline-node-fx")) return;
        ev.stopPropagation();
        startRename(art, st, nid);
      });
      const r = g.getBoundingClientRect();
      const left = r.left - fxRect.left, top = r.top - fxRect.top;
      const grp = document.createElement("div");
      grp.className = "inline-node-fx";
      grp.style.left = left + "px";
      grp.style.top = top + "px";
      grp.style.width = r.width + "px";
      grp.style.height = r.height + "px";
      grp.innerHTML =
        `<button type="button" class="ifx ifx-add" title="Clique: nova etapa · Arraste até uma caixa pra ligar">+</button>
         <button type="button" class="ifx ifx-shape" title="Alternar tipo: etapa / decisão / notificação"></button>
         <button type="button" class="ifx ifx-del" title="Excluir etapa">×</button>`;
      const SHAPE_GLYPH = { step: "▭", botao: "▢", decision: "◇", notif: "🔔" };
      const shapeBtn = grp.querySelector(".ifx-shape");
      shapeBtn.textContent = SHAPE_GLYPH[node.shape] || "▭";
      // destinatário: só faz sentido em notificação
      if (node.shape === "notif") {
        const recBtn = document.createElement("button");
        recBtn.type = "button";
        recBtn.className = "ifx ifx-recipient";
        recBtn.textContent = "👤";
        recBtn.title = (node.to ? NOTIF_PHRASE[node.to] : "Sem destinatário") + " — clique pra trocar";
        grp.appendChild(recBtn);
        recBtn.addEventListener("click", (ev) => {
          ev.stopPropagation();
          const order = ["", ...NOTIF_RECIPIENTS];
          node.to = order[(order.indexOf(node.to || "") + 1) % order.length];
          commitInline(art, st);
        });
      }
      fx.appendChild(grp);
      // manter os botões visíveis enquanto o mouse está no nó ou no grupo;
      // e registrar qual caixa está sob o cursor (pra tecla Delete)
      const show = () => { grp.classList.add("hot"); st.hoverNodeId = nid; };
      const hide = () => { grp.classList.remove("hot"); if (st.hoverNodeId === nid) st.hoverNodeId = null; };
      g.addEventListener("mouseenter", show); g.addEventListener("mouseleave", hide);
      grp.addEventListener("mouseenter", show); grp.addEventListener("mouseleave", hide);
      // + : clique cria uma etapa ligada; arrastar até outra caixa liga nela
      grp.querySelector(".ifx-add").addEventListener("mousedown", (ev) => {
        if (ev.button !== 0) return;
        ev.preventDefault(); ev.stopPropagation();
        startConnectDrag(art, st, nid, ev);
      });
      shapeBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const order = ["step", "botao", "decision", "notif"];
        node.shape = order[(order.indexOf(node.shape) + 1) % order.length];
        commitInline(art, st);
      });
      grp.querySelector(".ifx-del").addEventListener("click", (ev) => {
        ev.stopPropagation();
        st.state.nodes = st.state.nodes.filter((n) => n.id !== nid);
        st.state.edges = st.state.edges.filter((e) => e.from !== nid && e.to !== nid);
        commitInline(art, st);
      });
    });

    // ---- arestas: clicar tracejа/solta; botão de inverter no meio ----
    const edgePaths = $$(".edgePaths path.flowchart-link, .edgePaths path", svg);
    const usedEdge = new Set();
    edgePaths.forEach((path) => {
      const edge = edgeForPath(path, st.state, usedEdge);
      if (!edge) return;
      path.classList.add("inline-edge");
      path.style.cursor = "pointer";
      // caminho invisível "gordo" pra facilitar o clique na seta fina
      const hit = path.cloneNode();
      hit.classList.add("inline-edge-hit");
      hit.removeAttribute("id");
      hit.style.stroke = "transparent";
      hit.style.strokeWidth = "12px";
      hit.style.fill = "none";
      hit.style.pointerEvents = "stroke";
      hit.style.cursor = "pointer";
      path.parentNode.insertBefore(hit, path.nextSibling);
      // controles da seta no meio dela (rótulo / inverter / excluir) — só aparecem ao passar o mouse nessa aresta
      try {
        const p = path.getPointAtLength(path.getTotalLength() / 2);
        const sp = svg.createSVGPoint(); sp.x = p.x; sp.y = p.y;
        const scr = sp.matrixTransform(path.getScreenCTM());
        const lx = scr.x - fxRect.left, ly = scr.y - fxRect.top;
        // 1 clique traceja/solta na hora; o rótulo fica no botão "Aa"
        const onClick = (ev) => { ev.stopPropagation(); edge.dotted = !edge.dotted; commitInline(art, st); };
        [hit, path].forEach((el) => el.addEventListener("click", onClick));
        const ctrls = document.createElement("div");
        ctrls.className = "inline-edge-fx";
        ctrls.style.left = lx + "px";
        ctrls.style.top = ly + "px";
        ctrls.innerHTML =
          `<button type="button" class="ifx ifx-edge-label" title="Rótulo da seta (ex.: Sim / Não)">Aa</button>
           <button type="button" class="ifx ifx-reverse" title="Inverter o sentido da seta">⇄</button>
           <button type="button" class="ifx ifx-edge-del" title="Excluir esta ligação">×</button>`;
        fx.appendChild(ctrls);
        ctrls.querySelector(".ifx-edge-label").addEventListener("click", (ev) => {
          ev.stopPropagation();
          startEdgeLabelEdit(art, st, edge.id, lx, ly);
        });
        ctrls.querySelector(".ifx-reverse").addEventListener("click", (ev) => {
          ev.stopPropagation();
          const t = edge.from; edge.from = edge.to; edge.to = t;
          commitInline(art, st);
        });
        ctrls.querySelector(".ifx-edge-del").addEventListener("click", (ev) => {
          ev.stopPropagation();
          st.state.edges = st.state.edges.filter((x) => x.id !== edge.id);
          commitInline(art, st);
        });
        let hideT = null;
        const showRev = () => { clearTimeout(hideT); ctrls.classList.add("hot"); st.hoverEdgeId = edge.id; };
        const hideRev = () => { hideT = setTimeout(() => ctrls.classList.remove("hot"), 120); if (st.hoverEdgeId === edge.id) st.hoverEdgeId = null; };
        [hit, path, ctrls].forEach((el) => { el.addEventListener("mouseenter", showRev); el.addEventListener("mouseleave", hideRev); });
      } catch (e) { /* getPointAtLength pode falhar em curvas raras — segue sem os controles */ }
    });
  }

  // arrastar do "+" de uma caixa até outra pra criar a ligação.
  // sem arrastar (só clique) mantém o atalho de criar uma etapa nova já ligada.
  function startConnectDrag(art, st, sourceId, downEv) {
    const canvas = art.querySelector(".diagram-canvas");
    const fx = canvas && canvas.querySelector(".inline-fx");
    const svg = canvas && canvas.querySelector("svg");
    if (!fx || !svg) return;
    const fxRect = fx.getBoundingClientRect();
    const toLocal = (cx, cy) => [cx - fxRect.left, cy - fxRect.top];
    // posições das caixas (fixas durante o arrasto)
    const nodes = $$("g.node", svg).map((g) => {
      const id = inlineNodeId(g); if (!id) return null;
      const r = g.getBoundingClientRect();
      return { id, g, r };
    }).filter(Boolean);
    const src = nodes.find((n) => n.id === sourceId);
    if (!src) return;
    const nodeAt = (cx, cy) => nodes.find((n) => cx >= n.r.left && cx <= n.r.right && cy >= n.r.top && cy <= n.r.bottom);

    // linha-fantasma que segue o cursor. Um <div> girado (não um <svg> aninhado,
    // que a regra global ".diagram-canvas svg { height:auto }" colapsava pra 0×0).
    const [sx, sy] = toLocal(src.r.left + src.r.width / 2, src.r.top + src.r.height / 2);
    const line = document.createElement("div");
    line.className = "inline-drag-line";
    line.style.left = sx + "px";
    line.style.top = sy + "px";
    fx.appendChild(line);
    const drawLine = (lx, ly) => {
      const dx = lx - sx, dy = ly - sy;
      line.style.width = Math.hypot(dx, dy) + "px";
      line.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
    };
    document.body.classList.add("inline-connecting");

    let dragging = false, hovered = null;
    const move = (e) => {
      const dx = e.clientX - downEv.clientX, dy = e.clientY - downEv.clientY;
      if (!dragging && Math.hypot(dx, dy) < 5) return;
      dragging = true;
      const [lx, ly] = toLocal(e.clientX, e.clientY);
      drawLine(lx, ly);
      const tgt = nodeAt(e.clientX, e.clientY);
      if (hovered && (!tgt || tgt.g !== hovered)) hovered.classList.remove("inline-drop-target");
      if (tgt && tgt.id !== sourceId) { tgt.g.classList.add("inline-drop-target"); hovered = tgt.g; }
      else hovered = tgt && tgt.id === sourceId ? hovered : null;
    };
    const up = (e) => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      document.body.classList.remove("inline-connecting");
      if (hovered) hovered.classList.remove("inline-drop-target");
      line.remove();
      if (!dragging) {
        // clique puro: cria etapa nova já ligada (atalho antigo)
        const id = newNodeId(st.state);
        st.state.nodes.push({ id, label: "Nova etapa", shape: "step" });
        st.state.edges.push({ id: newEdgeId(st.state), from: sourceId, to: id, label: "", dotted: false });
        commitInline(art, st, id);
        return;
      }
      const tgt = nodeAt(e.clientX, e.clientY);
      if (!tgt || tgt.id === sourceId) return;   // soltou no vazio (ou nela mesma): cancela
      const dup = st.state.edges.some((ed) => ed.from === sourceId && ed.to === tgt.id);
      if (dup) { toast("Essas caixas já estão ligadas."); return; }
      // ligação que envolve notificação nasce tracejada (aviso lateral, não fluxo principal)
      const isNotif = (id) => { const n = st.state.nodes.find((x) => x.id === id); return n && n.shape === "notif"; };
      const dotted = isNotif(sourceId) || isNotif(tgt.id);
      st.state.edges.push({ id: newEdgeId(st.state), from: sourceId, to: tgt.id, label: "", dotted });
      commitInline(art, st);
      toast(dotted ? "Notificação ligada ao lado" : "Ligação criada");
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  }

  // casa um <path> de aresta renderizado com a aresta do estado.
  // o Mermaid expõe o par origem/destino em data-id (ex.: "L_B_B_0"); o id do
  // elemento vem prefixado ("mmd-2-L_B_B_0"), então preferimos o data-id.
  function edgeForPath(path, state, used) {
    const raw = path.getAttribute("data-id") || path.id || "";
    const m = /L[_-](.+?)[_-](.+?)[_-]\d+$/.exec(raw);
    let from = null, to = null;
    if (m) { from = m[1]; to = m[2]; }
    let cands = state.edges;
    if (from && to) cands = state.edges.filter((e) => e.from === from && e.to === to);
    const pick = cands.find((e) => !used.has(e.id)) || cands[0];
    if (pick) used.add(pick.id);
    return pick || null;
  }

  // renomear uma etapa direto sobre a caixa (input flutuante, sem janelinha)
  function startRename(art, st, nid) {
    const canvas = art.querySelector(".diagram-canvas");
    const fx = canvas.querySelector(".inline-fx");
    const svg = canvas.querySelector("svg");
    if (!fx || !svg) return;
    const g = $$("g.node", svg).find((x) => inlineNodeId(x) === nid);
    const node = st.state.nodes.find((n) => n.id === nid);
    if (!g || !node) return;
    fx.querySelector(".inline-rename")?.remove();
    const fxRect = fx.getBoundingClientRect();
    const r = g.getBoundingClientRect();
    const inp = document.createElement("input");
    inp.type = "text";
    inp.className = "inline-rename";
    inp.value = node.label || "";
    inp.style.left = (r.left - fxRect.left - 6) + "px";
    inp.style.top = (r.top - fxRect.top + r.height / 2 - 15) + "px";
    inp.style.width = Math.max(120, r.width + 12) + "px";
    fx.appendChild(inp);
    setTimeout(() => { inp.focus(); inp.select(); }, 10);
    let done = false;
    const commit = (save) => {
      if (done) return; done = true;
      if (save) { node.label = inp.value; commitInline(art, st); }
      else { inp.remove(); }
    };
    inp.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); commit(true); }
      else if (ev.key === "Escape") { ev.preventDefault(); commit(false); }
      ev.stopPropagation();
    });
    inp.addEventListener("blur", () => commit(true));
    inp.addEventListener("click", (ev) => ev.stopPropagation());
  }

  // rotular uma seta direto no meio dela (ex.: Sim / Não numa decisão)
  function startEdgeLabelEdit(art, st, edgeId, lx, ly) {
    const canvas = art.querySelector(".diagram-canvas");
    const fx = canvas && canvas.querySelector(".inline-fx");
    const edge = st.state.edges.find((e) => e.id === edgeId);
    if (!fx || !edge) return;
    fx.querySelector(".inline-rename")?.remove();
    const inp = document.createElement("input");
    inp.type = "text";
    inp.className = "inline-rename inline-edge-input";
    inp.value = edge.label || "";
    inp.placeholder = "rótulo (ex.: Sim)";
    inp.style.left = (lx - 55) + "px";
    inp.style.top = (ly - 14) + "px";
    inp.style.width = "110px";
    fx.appendChild(inp);
    setTimeout(() => { inp.focus(); inp.select(); }, 10);
    let done = false;
    const commit = (save) => {
      if (done) return; done = true;
      if (save) { edge.label = inp.value; commitInline(art, st); }
      else { inp.remove(); }
    };
    inp.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); commit(true); }
      else if (ev.key === "Escape") { ev.preventDefault(); commit(false); }
      ev.stopPropagation();
    });
    inp.addEventListener("blur", () => commit(true));
    inp.addEventListener("click", (ev) => ev.stopPropagation());
  }

  // atalhos de teclado enquanto um card está em edição inline
  document.addEventListener("keydown", (e) => {
    const art = $(".diagram.editing");
    if (!art) return;
    const st = inlineState.get(Number(art.dataset.id));
    if (!st) return;
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || "");
    // Ctrl/Cmd+Z desfaz
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && (e.key === "z" || e.key === "Z")) {
      if (typing) return;   // deixa o desfazer nativo do campo de texto
      e.preventDefault(); undoInline(art, st); return;
    }
    // Delete/Backspace apaga a caixa (ou a seta) sob o mouse
    if ((e.key === "Delete" || e.key === "Backspace") && !typing) {
      if (st.hoverNodeId) {
        e.preventDefault();
        const nid = st.hoverNodeId; st.hoverNodeId = null;
        st.state.nodes = st.state.nodes.filter((n) => n.id !== nid);
        st.state.edges = st.state.edges.filter((ed) => ed.from !== nid && ed.to !== nid);
        commitInline(art, st);
      } else if (st.hoverEdgeId) {
        e.preventDefault();
        const eid = st.hoverEdgeId; st.hoverEdgeId = null;
        st.state.edges = st.state.edges.filter((ed) => ed.id !== eid);
        commitInline(art, st);
      }
    }
  });

  $$(".view-tab").forEach((t) => t.addEventListener("click", () => switchView(t.dataset.view)));
  $("#btn-add-diagram").addEventListener("click", () => openDiagramModal("create"));
  $("#diagrams-empty-add").addEventListener("click", () => openDiagramModal("create"));
  diagramForm.addEventListener("submit", submitDiagramForm);
  // builder: adicionar etapa / ligação
  $("#add-node").addEventListener("click", () => {
    builder.nodes.push({ id: newNodeId(), label: "Nova etapa", shape: "step" });
    renderNodes(); renderEdges(); scheduleSync();
  });
  $("#add-edge").addEventListener("click", () => {
    if (!builder.nodes.length) { toast("Adicione ao menos uma etapa primeiro.", true); return; }
    const first = builder.nodes[0].id;
    const second = (builder.nodes[1] || builder.nodes[0]).id;
    builder.edges.push({ id: "e" + (++builder.eSeq), from: first, to: second, label: "", dotted: false });
    renderEdges(); scheduleSync();
  });
  // builder: sentido (vertical/horizontal)
  $$('input[name="builder-dir"]', diagramForm).forEach((r) => {
    r.addEventListener("change", (ev) => { if (ev.target.checked) { builder.dir = ev.target.value; scheduleSync(); } });
  });
  // modo avançado: edição manual do código volta pro builder (best-effort)
  diagramSource.addEventListener("input", () => {
    if (syncingCode) return;
    manualCode = true;
    const state = parseMermaid(diagramSource.value);
    if (state.nodes.length) { builder = state; renderNodes(); renderEdges(); }
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => renderPreview(diagramSource.value), 300);
  });
  // popover de edição direto no desenho
  $("#mm-pop-label").addEventListener("input", (ev) => {
    const node = builder.nodes.find((n) => n.id === popNodeId);
    if (!node) return;
    node.label = ev.target.value;
    const inp = document.querySelector(`#nodes-list .builder-row[data-id="${popNodeId}"] .b-label`);
    if (inp) inp.value = ev.target.value;
    scheduleSync();
  });
  $("#mm-pop-shape").addEventListener("change", (ev) => {
    const node = builder.nodes.find((n) => n.id === popNodeId);
    if (!node) return;
    node.shape = ev.target.value;
    renderNodes(); scheduleSync();
  });
  $("#mm-pop-add").addEventListener("click", () => {
    if (!popNodeId) return;
    const id = newNodeId();
    builder.nodes.push({ id, label: "Nova etapa", shape: "step" });
    builder.edges.push({ id: "e" + (++builder.eSeq), from: popNodeId, to: id, label: "", dotted: false });
    renderNodes(); renderEdges();
    pendingSelectId = id;   // abre o popover já na nova etapa
    scheduleSync();
  });
  $("#mm-pop-del").addEventListener("click", () => {
    if (!popNodeId) return;
    const id = popNodeId;
    builder.nodes = builder.nodes.filter((n) => n.id !== id);
    builder.edges = builder.edges.filter((e) => e.from !== id && e.to !== id);
    closeNodePopover();
    renderNodes(); renderEdges(); scheduleSync();
  });
  $("#mm-pop-close").addEventListener("click", closeNodePopover);
  // clicar no fundo da pré-visualização fecha o popover (clique numa caixa não borbulha)
  $("#diagram-preview").addEventListener("click", () => closeNodePopover());

  $("#diagram-close").addEventListener("click", closeDiagramModal);
  $("#diagram-cancel").addEventListener("click", closeDiagramModal);
  diagramModal.addEventListener("click", (e) => { if (e.target.id === "diagram-modal") closeDiagramModal(); });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || diagramModal.hidden) return;
    if (!nodePop.hidden) { closeNodePopover(); return; }   // Esc fecha o popover antes do modal
    closeDiagramModal();
  });
  // título/badge iniciais coerentes com o fluxo atual
  onFlowChangedForDiagrams();

  // ---------------- situações (cenários com estágios do chamado) ----------------
  // Cada Situação descreve um cenário completo (ex.: "chamado sem aceite") e se
  // desdobra em vários estágios do chamado — cada estágio é um mini caso de teste
  // (status, observações e prints próprios). Vive dentro do fluxo, ao lado dos
  // Grupos A/B/C/D, sem misturar com eles.
  let SITUACOES = [];
  let situacoesLoaded = false;
  const expandedSituacoes = new Set();   // codes das situações abertas (recolhidas por padrão)
  const sitActiveFilters = { situacao: "", frente: "", status: "" };
  const forcedOpenSituacoes = new Set();   // codes abertas TEMPORARIAMENTE por um filtro ativo (não mexe em expandedSituacoes)
  const STANDARD_STAGES = [
    "01 · Criar OS", "02 · Buscando Técnico", "03 · Téc. Aceitou", "04 · Agendado",
    "05 · Téc. em Deslocamento", "06 · Aguardando Liberação", "07 · Téc. em Atendimento",
    "08 · Acompanhamento N2", "09 · Aguardando RAT", "10 · Em Revisão",
    "11 · Atividade Concluída", "12 · Notificações (transversal)",
  ];

  function situacaoFlow(s) { return s.fluxo || "C"; }
  function findSituacao(code) { return SITUACOES.find((s) => s.code === code); }
  function findEstagio(sitCode, estagioId) {
    const s = findSituacao(sitCode);
    return s ? s.estagios.find((e) => e.id === estagioId) : null;
  }

  async function loadSituacoes() {
    if (!situacoesLoaded) $("#situacoes-loading").hidden = false;
    try {
      SITUACOES = await api("/api/situacoes");
      situacoesLoaded = true;
      $("#situacoes-loading").hidden = true;
      renderSituacoes();
    } catch (e) {
      $("#situacoes-loading").textContent = "Erro ao carregar situações: " + e.message;
    }
  }

  function estagioShotThumb(shot, sitCode, estagioId) {
    return `<div class="shot-thumb" data-shot="${shot.id}">
      <img src="/api/situacao-screenshots/${shot.id}" alt="${esc(shot.filename)}" loading="lazy">
      <button class="del" data-del-sit-shot="${shot.id}" data-sit="${esc(sitCode)}" data-estagio="${estagioId}" title="Remover print">✕</button>
    </div>`;
  }

  function estagioObsList(observations) {
    if (!observations || !observations.length) {
      return `<div class="obs-empty">Nenhuma observação ainda.</div>`;
    }
    return observations.map((o) => `<div class="obs-item">
        <div class="obs-item-head"><span class="obs-author">${esc(o.autor || "Anônimo")}</span><span class="obs-when">${fmtWhen(o.created_at)}</span></div>
        <div class="obs-text">${esc(o.texto)}</div>
      </div>`).join("");
  }

  function estagioCard(sit, e, idx) {
    const stCode = STATUS_CODE[e.status] || "nt";
    const frontCode = FRONT_CODE[e.frente] || "trv";
    const shots = (e.screenshots || []).map((s) => estagioShotThumb(s, sit.code, e.id)).join("");
    // o texto da situação (título/descrição) entra no search de cada estágio —
    // assim buscar pelo nome do cenário mostra todos os estágios dele, mesmo que
    // o texto buscado não apareça no estágio em si
    const search = (sit.titulo + " " + sit.descricao + " " + e.nome + " " + e.resultado_esperado).toLowerCase();
    return `<article class="estagio st-${stCode}" data-sit="${esc(sit.code)}" data-estagio-id="${e.id}"
        data-frente="${esc(e.frente)}" data-status="${esc(e.status)}" data-search="${esc(search)}">
      <div class="estagio-head">
        <span class="estagio-num">Estágio ${idx}</span>
        <span class="tag front-${frontCode}">${esc(e.frente)}</span>
        <span class="estagio-nome">${esc(e.nome)}</span>
        <div class="estagio-actions">
          <button type="button" class="case-icon-btn" data-edit-estagio title="Editar estágio" aria-label="Editar">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
          </button>
          <button type="button" class="case-icon-btn danger" data-del-estagio title="Excluir estágio" aria-label="Excluir">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </div>
      ${e.passos ? `<div class="blk wide"><div class="k">Passos</div><div class="v">${esc(e.passos)}</div></div>` : ""}
      <div class="blk wide result"><div class="k">Resultado esperado</div><div class="v">${esc(e.resultado_esperado)}</div></div>
      <div class="estagio-foot">
        <div class="status-row">
          <div class="status-btns">
            ${STATUSES.map((s) => `<button class="sbtn ${s === e.status ? "active" : ""}" data-s="${s}">${s}</button>`).join("")}
          </div>
          ${e.status === "Reprovado" ? `<button type="button" class="adjust-btn" data-adjust title="Marca como corrigido e devolve pra fila de reteste">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            Ajustado, retestar
          </button>` : ""}
        </div>
        <div class="case-meta">Testado por <span class="who">${e.testado_por ? esc(e.testado_por) : "—"}</span><span class="when">${e.testado_por ? " · " + fmtWhen(e.updated_at) : ""}</span></div>
        <div class="obs-row">
          <div class="obs-list">${estagioObsList(e.observations)}</div>
          <div class="obs-add">
            <textarea class="obs-input" rows="1" placeholder="Adicionar observação..."></textarea>
            <button type="button" class="obs-add-btn">Adicionar</button>
          </div>
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

  function situacaoProgress(sit) {
    const total = sit.estagios.length;
    const done = sit.estagios.filter((e) => e.status !== "Não testado").length;
    const pct = total ? Math.round((done / total) * 100) : 0;
    return { total, done, pct };
  }

  function situacaoCard(sit) {
    const { total, done, pct } = situacaoProgress(sit);
    const open = expandedSituacoes.has(sit.code);
    const stages = sit.estagios.map((e, i) => estagioCard(sit, e, i + 1)).join("");
    return `<section class="situacao ${open ? "" : "collapsed"}" data-code="${esc(sit.code)}">
      <div class="situacao-head">
        <button type="button" class="situacao-toggle" aria-label="Abrir/recolher" aria-expanded="${open ? "true" : "false"}">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
        <span class="situacao-badge">Situação</span>
        <span class="situacao-title">${esc(sit.titulo)}</span>
        <span class="situacao-progress-mini">${done}/${total}</span>
        <div class="case-actions">
          <button type="button" class="case-icon-btn" data-edit-situacao="${esc(sit.code)}" title="Editar situação" aria-label="Editar">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
          </button>
          <button type="button" class="case-icon-btn danger" data-del-situacao="${esc(sit.code)}" title="Excluir situação" aria-label="Excluir">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
        <span class="situacao-code-mini">${esc(sit.code)}</span>
      </div>
      <div class="situacao-body">
        <p class="situacao-desc">${esc(sit.descricao)}</p>
        <div class="situacao-progress">
          <div class="situacao-bar"><i style="width:${pct}%"></i></div>
          <span class="situacao-progress-label">${done}/${total} estágios testados</span>
        </div>
        <div class="reg-row">
          <label class="reg-field">
            <span class="reg-k">Chamado testado</span>
            <input class="situacao-chamado" type="text" value="${esc(sit.chamado || "")}" placeholder="qual chamado foi testado nesta situação" autocomplete="off">
          </label>
        </div>
        <div class="situacao-stages">${stages}</div>
        <button type="button" class="add-btn situacao-add-estagio" data-add-estagio="${esc(sit.code)}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Estágio
        </button>
      </div>
    </section>`;
  }

  function renderSituacoes() {
    const flowSits = SITUACOES.filter((s) => situacaoFlow(s) === currentFlow);
    const emptyEl = $("#situacoes-empty");
    if (!flowSits.length) {
      $("#situacoes").innerHTML = "";
      $("#situacoes-empty-badge").textContent = "Fluxo " + currentFlow;
      emptyEl.hidden = false;
      buildSituacaoFilters(flowSits);
      updateSituacaoStats(flowSits);
      return;
    }
    emptyEl.hidden = true;
    $("#situacoes").innerHTML = flowSits.map(situacaoCard).join("");
    attachSituacaoHandlers();
    buildSituacaoFilters(flowSits);
    applySituacaoFilters();
    updateSituacaoStats(flowSits);
  }

  // ---------------- situações: KPIs + filtros ----------------
  function allEstagios(flowSits) {
    return flowSits.flatMap((s) => s.estagios);
  }

  function updateSituacaoStats(flowSits) {
    const counts = { "Não testado": 0, "Aprovado": 0, "Reprovado": 0, "Bloqueado": 0, "N/A": 0 };
    allEstagios(flowSits).forEach((e) => { counts[e.status] = (counts[e.status] || 0) + 1; });
    $("#sit-stat-nt").textContent = counts["Não testado"];
    $("#sit-stat-ok").textContent = counts["Aprovado"];
    $("#sit-stat-bad").textContent = counts["Reprovado"];
    $("#sit-stat-warn").textContent = counts["Bloqueado"];
    $("#sit-stat-na").textContent = counts["N/A"];
    $$("#sit-stat-strip .stat").forEach((t) => t.classList.toggle("active", t.dataset.k === sitActiveFilters.status));
  }
  $$("#sit-stat-strip .stat").forEach((tile) => {
    tile.addEventListener("click", () => {
      const k = tile.dataset.k;
      sitActiveFilters.status = sitActiveFilters.status === k ? "" : k;
      $$("#sit-chips-status .chip").forEach((b) => b.classList.toggle("active", b.dataset.val === sitActiveFilters.status));
      $$("#sit-stat-strip .stat").forEach((t) => t.classList.toggle("active", t.dataset.k === sitActiveFilters.status));
      applySituacaoFilters();
    });
  });

  function buildSitChipGroup(containerId, filterKey, values, colorMap) {
    const el = document.getElementById(containerId);
    el.innerHTML = values.map(({ label, val }) => {
      const colorClass = colorMap && colorMap[label] ? colorMap[label] : "";
      const active = sitActiveFilters[filterKey] === val;
      return `<button type="button" class="chip ${colorClass} ${active ? "active" : ""}" data-key="${filterKey}" data-val="${esc(val)}">${esc(label)}</button>`;
    }).join("");
    $$(".chip", el).forEach((btn) => {
      btn.addEventListener("click", () => {
        sitActiveFilters[btn.dataset.key] = btn.dataset.val;
        $$(".chip", el).forEach((b) => b.classList.toggle("active", b.dataset.val === btn.dataset.val));
        if (filterKey === "status") $$("#sit-stat-strip .stat").forEach((t) => t.classList.toggle("active", t.dataset.k === sitActiveFilters.status));
        applySituacaoFilters();
      });
    });
  }

  function buildSituacaoFilters(flowSits) {
    const uniq = (arr) => [...new Set(arr)];
    buildSitChipGroup("sit-chips-situacao", "situacao",
      [{ label: "Todas", val: "" }, ...flowSits.map((s) => ({ label: s.titulo, val: s.code }))]);
    buildSitChipGroup("sit-chips-frente", "frente",
      [{ label: "Todas", val: "" }, ...uniq(allEstagios(flowSits).map((e) => e.frente)).map((v) => ({ label: v, val: v }))],
      FRENT_CHIP_CLASS);
    buildSitChipGroup("sit-chips-status", "status",
      [{ label: "Todos", val: "" }, ...STATUSES.map((v) => ({ label: v, val: v }))],
      STATUS_CHIP_CLASS);
  }

  function updateSituacaoFiltersActiveCount() {
    const n = ["situacao", "frente", "status"].filter((k) => sitActiveFilters[k]).length;
    const el = $("#sit-filters-active-count");
    if (el) { el.textContent = n; el.hidden = n === 0; }
  }

  function applySituacaoFilters() {
    const { situacao: sitSel, frente: fr, status: st } = sitActiveFilters;
    const q = $("#sit-f-busca").value.trim().toLowerCase();
    const anyActive = !!(sitSel || fr || st || q);

    $$(".situacao").forEach((card) => {
      const sitCode = card.dataset.code;
      if (sitSel && sitCode !== sitSel) {
        card.classList.add("sit-hidden");
        return;
      }
      card.classList.remove("sit-hidden");

      let anyVisible = false;
      $$(".estagio", card).forEach((row) => {
        let ok = true;
        if (fr && row.dataset.frente !== fr) ok = false;
        if (st && row.dataset.status !== st) ok = false;
        if (q && !row.dataset.search.includes(q)) ok = false;
        row.classList.toggle("hidden", !ok);
        if (ok) anyVisible = true;
      });

      if (anyActive && !anyVisible) card.classList.add("sit-hidden");

      // enquanto um filtro está ativo, abre temporariamente os cards com resultado
      // (sem mexer no estado de aberto/fechado que o usuário escolheu)
      if (anyActive && anyVisible) {
        card.classList.add("filter-open");
        forcedOpenSituacoes.add(sitCode);
      } else if (forcedOpenSituacoes.has(sitCode)) {
        card.classList.remove("filter-open");
        forcedOpenSituacoes.delete(sitCode);
      }
    });

    updateSituacaoFiltersActiveCount();
  }
  $("#sit-f-busca").addEventListener("input", applySituacaoFilters);

  const sitFiltersToggle = $("#sit-filters-toggle");
  const sitFiltersBody = $("#sit-filters-body");
  sitFiltersToggle.addEventListener("click", () => {
    const open = sitFiltersBody.hidden;
    sitFiltersBody.hidden = !open;
    sitFiltersToggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

  function attachSituacaoHandlers() {
    $$(".situacao").forEach((card) => {
      const sitCode = card.dataset.code;

      const editBtn = $(`[data-edit-situacao="${cssEscape(sitCode)}"]`, card);
      if (editBtn) editBtn.addEventListener("click", () => openSituacaoModal("edit", sitCode));
      const delBtn = $(`[data-del-situacao="${cssEscape(sitCode)}"]`, card);
      if (delBtn) delBtn.addEventListener("click", () => deleteSituacao(sitCode));
      const addEstBtn = $(`[data-add-estagio="${cssEscape(sitCode)}"]`, card);
      if (addEstBtn) addEstBtn.addEventListener("click", () => openEstagioModal("create", sitCode));

      // um único "chamado testado" vale pra situação inteira (não por estágio)
      const chamadoInput = $(".situacao-chamado", card);
      if (chamadoInput) chamadoInput.addEventListener("change", async () => {
        try {
          await api(`/api/situacoes/${encodeURIComponent(sitCode)}`, {
            method: "PATCH", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chamado: chamadoInput.value.trim() }),
          });
          await refreshSituacao(sitCode);
          toast("Chamado salvo");
        } catch (e) { toast("Erro ao salvar: " + e.message, true); }
      });

      // abrir/recolher pelo cabeçalho (menos os botões de ação)
      $(".situacao-head", card).addEventListener("click", (ev) => {
        if (ev.target.closest(".case-actions")) return;
        const nowOpen = card.classList.toggle("collapsed") === false;
        card.querySelector(".situacao-toggle").setAttribute("aria-expanded", nowOpen ? "true" : "false");
        if (nowOpen) expandedSituacoes.add(sitCode); else expandedSituacoes.delete(sitCode);
      });

      $$(".estagio", card).forEach((row) => attachOneEstagioHandlers(row, sitCode));
    });
  }

  function attachOneEstagioHandlers(row, sitCode) {
    const estagioId = parseInt(row.dataset.estagioId, 10);

    const editBtn = $("[data-edit-estagio]", row);
    if (editBtn) editBtn.addEventListener("click", () => openEstagioModal("edit", sitCode, estagioId));
    const delBtn = $("[data-del-estagio]", row);
    if (delBtn) delBtn.addEventListener("click", () => deleteEstagio(sitCode, estagioId));

    $$(".sbtn", row).forEach((btn) => {
      btn.addEventListener("click", async () => {
        const s = btn.dataset.s;
        try {
          await api(`/api/situacoes/${encodeURIComponent(sitCode)}/estagios/${estagioId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: s, testado_por: testerName() || undefined }),
          });
          await refreshSituacao(sitCode);
          toast(`Estágio → ${s}`);
        } catch (e) { toast("Erro ao salvar: " + e.message, true); }
      });
    });

    const adjustBtn = $("[data-adjust]", row);
    if (adjustBtn) adjustBtn.addEventListener("click", async () => {
      adjustBtn.disabled = true;
      try {
        await api(`/api/situacoes/${encodeURIComponent(sitCode)}/estagios/${estagioId}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "Não testado" }),
        });
        await api(`/api/situacoes/${encodeURIComponent(sitCode)}/estagios/${estagioId}/observacoes`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ texto: "Ajustado, pronto para novo teste.", autor: testerName() || "LP Digital" }),
        });
        await refreshSituacao(sitCode);
        toast("Marcado como ajustado — volta pra fila de teste");
      } catch (e) { toast("Erro ao marcar como ajustado: " + e.message, true); adjustBtn.disabled = false; }
    });

    const obsInput = $(".obs-input", row);
    const obsBtn = $(".obs-add-btn", row);
    const submitObs = async () => {
      const texto = obsInput.value.trim();
      if (!texto) return;
      obsBtn.disabled = true;
      try {
        await api(`/api/situacoes/${encodeURIComponent(sitCode)}/estagios/${estagioId}/observacoes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ texto, autor: testerName() || undefined }),
        });
        await refreshSituacao(sitCode);
        toast("Observação adicionada");
      } catch (e) {
        toast("Erro ao salvar observação: " + e.message, true);
      } finally {
        obsBtn.disabled = false;
      }
    };
    obsBtn.addEventListener("click", submitObs);
    obsInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitObs(); }
    });

    const fileInput = $(".shot-input", row);
    const zone = $(".upload-zone", row);
    fileInput.addEventListener("change", () => { if (fileInput.files[0]) uploadEstagioShot(sitCode, estagioId, fileInput.files[0], zone); });
    ["dragover", "dragenter"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("dragover"); }));
    ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("dragover"); }));
    zone.addEventListener("drop", (e) => {
      const f = e.dataTransfer.files[0];
      if (f) uploadEstagioShot(sitCode, estagioId, f, zone);
    });

    $$(".shots-grid .shot-thumb", row).forEach((thumb) => {
      const img = $("img", thumb);
      if (!img) return;
      img.addEventListener("click", () => {
        const shotId = parseInt(thumb.dataset.shot, 10);
        const e = findEstagio(sitCode, estagioId);
        const slides = (e.screenshots || []).map((s) => ({ id: s.id, filename: s.filename, estagio: e.nome }));
        const idx = slides.findIndex((s) => s.id === shotId);
        openSituacaoCarousel(slides, idx < 0 ? 0 : idx, `Evidências — ${e.nome}`);
      });
    });
    $$(".del[data-del-sit-shot]", row).forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm("Remover este print?")) return;
        try {
          await api(`/api/situacao-screenshots/${btn.dataset.delSitShot}`, { method: "DELETE" });
          await refreshSituacao(sitCode);
          toast("Print removido");
        } catch (err) { toast("Erro ao remover: " + err.message, true); }
      });
    });
  }

  // Prints não têm um carrossel de apresentação próprio como os casos de teste
  // (evidências por situação são poucas) — abre no lightbox simples em sequência.
  function openSituacaoCarousel(slides, startIndex, title) {
    if (!slides.length) return;
    openLightbox(`/api/situacao-screenshots/${slides[Math.max(0, startIndex)].id}`);
  }

  async function refreshSituacao(sitCode) {
    const updated = await api(`/api/situacoes/${encodeURIComponent(sitCode)}`);
    const i = SITUACOES.findIndex((s) => s.code === sitCode);
    if (i >= 0) SITUACOES[i] = updated; else SITUACOES.push(updated);
    renderSituacoes();
  }

  async function uploadEstagioShot(sitCode, estagioId, file, zone) {
    zone.textContent = "…";
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (testerName()) fd.append("uploaded_by", testerName());
      await api(`/api/situacoes/${encodeURIComponent(sitCode)}/estagios/${estagioId}/screenshots`, { method: "POST", body: fd });
      await refreshSituacao(sitCode);
      toast("Print anexado");
    } catch (e) {
      toast("Erro ao subir print: " + e.message, true);
      zone.textContent = "+";
    }
  }

  async function deleteEstagio(sitCode, estagioId) {
    if (!confirm("Excluir este estágio da situação?")) return;
    try {
      await api(`/api/situacoes/${encodeURIComponent(sitCode)}/estagios/${estagioId}`, { method: "DELETE" });
      await refreshSituacao(sitCode);
      toast("Estágio excluído");
    } catch (e) { toast("Erro ao excluir: " + e.message, true); }
  }

  function onFlowChangedForSituacoes() {
    $("#situacoes-title").textContent = "Situações do Fluxo " + currentFlow;
    $("#situacoes-empty-badge").textContent = "Fluxo " + currentFlow;
    if (currentView === "situacoes") renderSituacoes();
  }

  // ---------------- modal: criar / editar / excluir situação ----------------
  let editingSituacaoCode = null;
  const situacaoModal = $("#situacao-modal");
  const situacaoForm = $("#situacao-form");
  const situacaoStubRow = $("#situacao-stub-row");

  function fillSituacaoStubSource() {
    const sel = $("#situacao-stub-source");
    sel.querySelectorAll("option[data-copy]").forEach((o) => o.remove());
    if (!SITUACOES.length) return;
    const group = document.createElement("optgroup");
    group.label = "Copiar estágios de…";
    SITUACOES.slice().sort((a, b) => a.titulo.localeCompare(b.titulo)).forEach((s) => {
      const o = document.createElement("option");
      o.value = "copiar:" + s.code;
      o.dataset.copy = "1";
      o.textContent = `${s.titulo} (${s.code}, ${s.estagios.length} estágio${s.estagios.length === 1 ? "" : "s"})`;
      group.appendChild(o);
    });
    sel.appendChild(group);
  }

  function openSituacaoModal(mode, code) {
    editingSituacaoCode = mode === "edit" ? code : null;
    $("#situacao-modal-title").textContent = mode === "edit" ? "Editar situação" : "Nova situação";
    const codeEl = $("#situacao-modal-code");
    situacaoStubRow.hidden = mode === "edit";
    if (mode === "edit") {
      const s = findSituacao(code);
      if (!s) return;
      codeEl.textContent = s.code; codeEl.hidden = false;
      situacaoForm.fluxo.value = situacaoFlow(s);
      situacaoForm.titulo.value = s.titulo || "";
      situacaoForm.descricao.value = s.descricao || "";
    } else {
      situacaoForm.reset();
      codeEl.hidden = true;
      situacaoForm.fluxo.value = currentFlow;
      fillSituacaoStubSource();
      $("#situacao-stub-source").value = "padrao";
    }
    situacaoModal.hidden = false;
    setTimeout(() => { try { situacaoForm.titulo.focus(); } catch (e) {} }, 30);
  }
  function closeSituacaoModal() { situacaoModal.hidden = true; editingSituacaoCode = null; }

  async function submitSituacaoForm(e) {
    e.preventDefault();
    const payload = {
      fluxo: situacaoForm.fluxo.value,
      titulo: situacaoForm.titulo.value.trim(),
      descricao: situacaoForm.descricao.value.trim(),
    };
    if (!payload.titulo) { toast("Informe o título da situação.", true); return; }
    if (!payload.descricao) { toast("Descreva o cenário.", true); return; }
    const stubSource = editingSituacaoCode ? "" : $("#situacao-stub-source").value;
    const copySourceCode = stubSource.startsWith("copiar:") ? stubSource.slice(7) : null;
    const saveBtn = $("#situacao-modal-save");
    saveBtn.disabled = true;
    try {
      let code = editingSituacaoCode;
      if (editingSituacaoCode) {
        await api(`/api/situacoes/${encodeURIComponent(editingSituacaoCode)}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        toast("Situação atualizada");
      } else {
        const created = await api("/api/situacoes", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        code = created.code;
        if (copySourceCode) {
          const source = findSituacao(copySourceCode);
          for (const e of (source ? source.estagios : [])) {
            await api(`/api/situacoes/${encodeURIComponent(code)}/estagios`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                nome: e.nome, frente: e.frente, passos: e.passos || "",
                resultado_esperado: e.resultado_esperado,
              }),
            });
          }
        } else if (stubSource === "padrao") {
          for (const nome of STANDARD_STAGES) {
            await api(`/api/situacoes/${encodeURIComponent(code)}/estagios`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                nome, frente: "A definir",
                resultado_esperado: "[PREENCHER] O que deve acontecer neste estágio, neste cenário.",
              }),
            });
          }
        }
        toast("Situação criada");
      }
      const targetFlow = payload.fluxo;
      await loadSituacoes();
      if (targetFlow !== currentFlow) setFlow(targetFlow);
      closeSituacaoModal();
    } catch (err) {
      toast("Erro ao salvar: " + err.message, true);
    } finally {
      saveBtn.disabled = false;
    }
  }

  async function deleteSituacao(code) {
    if (!confirm(`Excluir a situação ${code}? Ela sai da lista (dá pra recriar depois).`)) return;
    try {
      await api(`/api/situacoes/${encodeURIComponent(code)}`, { method: "DELETE" });
      SITUACOES = SITUACOES.filter((s) => s.code !== code);
      renderSituacoes();
      toast("Situação excluída");
    } catch (err) {
      toast("Erro ao excluir: " + err.message, true);
    }
  }

  situacaoForm.addEventListener("submit", submitSituacaoForm);
  $("#situacao-modal-close").addEventListener("click", closeSituacaoModal);
  $("#situacao-modal-cancel").addEventListener("click", closeSituacaoModal);
  situacaoModal.addEventListener("click", (e) => { if (e.target.id === "situacao-modal") closeSituacaoModal(); });
  $("#btn-add-situacao").addEventListener("click", () => openSituacaoModal("create"));
  $("#situacoes-empty-add").addEventListener("click", () => openSituacaoModal("create"));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !situacaoModal.hidden) closeSituacaoModal(); });

  // ---------------- modal: adicionar / editar estágio dentro de uma situação ----------------
  let editingEstagio = null;   // { sitCode, estagioId } | null
  let estagioModalSitCode = null;   // situação-alvo ao criar um estágio novo
  const estagioModal = $("#estagio-modal");
  const estagioForm = $("#estagio-form");

  function openEstagioModal(mode, sitCode, estagioId) {
    estagioModalSitCode = sitCode;
    editingEstagio = mode === "edit" ? { sitCode, estagioId } : null;
    $("#estagio-modal-title").textContent = mode === "edit" ? "Editar estágio" : "Novo estágio";
    const sit = findSituacao(sitCode);
    $("#estagio-modal-sit").textContent = sit ? sit.titulo : sitCode;
    if (mode === "edit") {
      const e = findEstagio(sitCode, estagioId);
      if (!e) return;
      estagioForm.nome.value = e.nome || "";
      estagioForm.frente.value = e.frente || "A definir";
      estagioForm.passos.value = e.passos || "";
      estagioForm.resultado_esperado.value = e.resultado_esperado || "";
    } else {
      estagioForm.reset();
      estagioForm.frente.value = "A definir";
    }
    estagioModal.hidden = false;
    setTimeout(() => { try { estagioForm.nome.focus(); } catch (e) {} }, 30);
  }
  function closeEstagioModal() { estagioModal.hidden = true; editingEstagio = null; }

  async function submitEstagioForm(e) {
    e.preventDefault();
    const payload = {
      nome: estagioForm.nome.value.trim(),
      frente: estagioForm.frente.value,
      passos: estagioForm.passos.value.trim(),
      resultado_esperado: estagioForm.resultado_esperado.value.trim(),
    };
    if (!payload.nome) { toast("Informe o nome do estágio.", true); return; }
    if (!payload.resultado_esperado) { toast("Informe o resultado esperado.", true); return; }
    const saveBtn = $("#estagio-modal-save");
    saveBtn.disabled = true;
    try {
      if (editingEstagio) {
        await api(`/api/situacoes/${encodeURIComponent(editingEstagio.sitCode)}/estagios/${editingEstagio.estagioId}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        await refreshSituacao(editingEstagio.sitCode);
        toast("Estágio atualizado");
      } else {
        await api(`/api/situacoes/${encodeURIComponent(estagioModalSitCode)}/estagios`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        await refreshSituacao(estagioModalSitCode);
        toast("Estágio criado");
      }
      closeEstagioModal();
    } catch (err) {
      toast("Erro ao salvar: " + err.message, true);
    } finally {
      saveBtn.disabled = false;
    }
  }

  estagioForm.addEventListener("submit", submitEstagioForm);
  $("#estagio-modal-close").addEventListener("click", closeEstagioModal);
  $("#estagio-modal-cancel").addEventListener("click", closeEstagioModal);
  estagioModal.addEventListener("click", (e) => { if (e.target.id === "estagio-modal") closeEstagioModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !estagioModal.hidden) closeEstagioModal(); });

  // ---------------- perfil (LP Digital / Faiston) ----------------
  const PERFIL_KEY = "fluxoc_perfil";
  const PERFIL_LABEL = { LP: "LP Digital", Faiston: "Faiston" };
  let PERFIL = localStorage.getItem(PERFIL_KEY) || "";
  const perfilModal = $("#perfil-modal");

  function applyPerfilChip() {
    const nameEl = $("#perfil-name"), dot = $("#perfil-dot");
    if (nameEl) nameEl.textContent = PERFIL ? PERFIL_LABEL[PERFIL] : "escolher";
    if (dot) dot.className = "perfil-dot" + (PERFIL ? (PERFIL === "LP" ? " lp" : " fai") : "");
  }
  function openPerfilGate(dismissable) {
    $("#perfil-modal-close").hidden = !dismissable;
    perfilModal.dataset.dismissable = dismissable ? "1" : "";
    perfilModal.hidden = false;
  }
  function closePerfilGate() { perfilModal.hidden = true; }

  async function tentarEntrar(perfil, senha) {
    try {
      const r = await api("/api/perfil/entrar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ perfil, senha }),
      });
      return !!r.ok;
    } catch (e) { return false; }
  }

  function setPerfil(p) {
    PERFIL = p;
    localStorage.setItem(PERFIL_KEY, p);
    applyPerfilChip();
    closePerfilGate();
    loadActivities();   // recarrega o "visto" do time escolhido
    if (typeof applyModuleVisibility === "function") applyModuleVisibility();
  }

  $$(".perfil-choice").forEach((b) => {
    b.addEventListener("click", async () => {
      const p = b.dataset.perfil;
      if (p === "Faiston") {
        $("#perfil-senha-box").hidden = false;
        $("#perfil-senha-input").focus();
        return;
      }
      setPerfil(p);
    });
  });

  async function confirmarSenhaFaiston() {
    const senha = $("#perfil-senha-input").value;
    const ok = await tentarEntrar("Faiston", senha);
    if (ok) {
      setPerfil("Faiston");
      $("#perfil-senha-box").hidden = true;
      $("#perfil-senha-input").value = "";
      $("#perfil-senha-erro").hidden = true;
    } else {
      $("#perfil-senha-erro").hidden = false;
    }
  }
  $("#perfil-senha-confirmar").addEventListener("click", confirmarSenhaFaiston);
  $("#perfil-senha-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") confirmarSenhaFaiston();
  });
  $("#perfil-chip").addEventListener("click", () => openPerfilGate(true));
  $("#perfil-modal-close").addEventListener("click", closePerfilGate);
  perfilModal.addEventListener("click", (e) => {
    if (e.target.id === "perfil-modal" && perfilModal.dataset.dismissable) closePerfilGate();
  });

  // ---------------- novidades (trilha de atividades) ----------------
  // Cada mudança vira um evento no servidor. O "novo" é por TIME (perfil): o
  // servidor guarda até que id de evento cada perfil já viu — o "login" da LP /
  // Faiston — então vale pra todo o time, em qualquer computador.
  let ACTIVITIES = [];
  let LAST_SEEN_ID = 0;
  const activityModal = $("#activity-modal");

  async function loadActivities() {
    if (!PERFIL) { const el = $("#activity-count"); if (el) el.hidden = true; return; }
    try {
      const [acts, seen] = await Promise.all([
        api(`/api/atividades?fluxo=${encodeURIComponent(currentFlow)}`),
        api(`/api/atividades/visto?perfil=${encodeURIComponent(PERFIL)}&fluxo=${encodeURIComponent(currentFlow)}`),
      ]);
      ACTIVITIES = acts;
      LAST_SEEN_ID = (seen && seen.last_seen_id) || 0;
    } catch (e) { ACTIVITIES = []; LAST_SEEN_ID = 0; }
    updateActivityCount();
  }

  function actIsNew(a) { return a.id > LAST_SEEN_ID; }

  function updateActivityCount() {
    const n = ACTIVITIES.filter(actIsNew).length;
    const el = $("#activity-count");
    if (el) { el.textContent = n > 99 ? "99+" : n; el.hidden = n === 0; }
  }

  const ACT_ICON = { status: "◉", obs: "💬", print: "🖼️", teste: "🧪", ponto: "📋", diagrama: "🗺️" };

  function renderActivityList(boundary) {
    const el = $("#activity-list");
    if (!ACTIVITIES.length) {
      el.innerHTML = `<div class="notes-empty">Nenhuma atividade registrada ainda neste fluxo.</div>`;
      return;
    }
    let html = "", divided = false, anyNew = false;
    ACTIVITIES.forEach((a) => {
      const isNew = a.id > boundary;
      if (isNew) anyNew = true;
      else if (anyNew && !divided) {
        html += `<div class="act-divider">acima: novo pra ${esc(PERFIL_LABEL[PERFIL] || "você")} · abaixo: já visto</div>`;
        divided = true;
      }
      // eventos de caso (FC-...) levam ao card; os de diagrama (case_code "diagrama:ID") não
      const goCode = a.case_code && !String(a.case_code).startsWith("diagrama:") ? a.case_code : "";
      html += `<div class="act-item ${isNew ? "is-new" : ""} ${goCode ? "act-go" : ""}" ${goCode ? `data-go="${esc(goCode)}" role="button" tabindex="0" title="Ir para o teste ${esc(goCode)}"` : ""}>
        <span class="act-icon">${ACT_ICON[a.tipo] || "•"}</span>
        <div class="act-body">
          <div class="act-text">${esc(a.texto)}</div>
          <div class="act-meta">${a.autor ? esc(a.autor) + " · " : ""}${fmtWhen(a.created_at)}${isNew ? ' · <b class="act-new">novo</b>' : ""}</div>
        </div>
        ${goCode ? '<span class="act-goto" aria-hidden="true">ver o teste →</span>' : ""}
      </div>`;
    });
    el.innerHTML = html;
    $$(".act-item.act-go", el).forEach((item) => {
      const go = () => goToCase(item.dataset.go);
      item.addEventListener("click", go);
      item.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
  }

  // leva da trilha de novidades até o card do teste: garante o fluxo/sub-aba
  // certos, limpa filtro que poderia esconder o card, rola até ele e destaca.
  function goToCase(code) {
    const c = findCase(code);
    closeActivityModal();
    if (c && caseFlow(c) !== currentFlow) setFlow(caseFlow(c));
    switchView("testes");
    if (activeFilters.status) {
      activeFilters.status = "";
      $$("#chips-status .chip").forEach((b) => b.classList.toggle("active", b.dataset.val === ""));
      applyFilters();
    }
    setTimeout(() => {
      const card = document.querySelector(`.case[data-code="${cssEscape(code)}"]`);
      if (!card) { toast("Esse teste não está mais na lista (pode ter sido excluído)."); return; }
      card.classList.remove("hidden");
      card.scrollIntoView({ behavior: "smooth", block: "center" });
      card.classList.add("case-flash");
      setTimeout(() => card.classList.remove("case-flash"), 1800);
    }, 80);
  }

  async function markSeen() {
    if (!PERFIL || !ACTIVITIES.length) return;
    const maxId = ACTIVITIES.reduce((m, a) => Math.max(m, a.id), 0);
    if (maxId <= LAST_SEEN_ID) return;
    try {
      await api("/api/atividades/visto", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ perfil: PERFIL, fluxo: currentFlow, last_seen_id: maxId }),
      });
      LAST_SEEN_ID = maxId;   // marca visto pro time todo; badge zera
      updateActivityCount();
    } catch (e) {}
  }

  function openActivityModal() {
    $("#activity-flow-label").textContent = "Fluxo " + currentFlow + " · " + (PERFIL_LABEL[PERFIL] || "");
    const boundary = LAST_SEEN_ID;       // fronteira do que era novo ao abrir
    renderActivityList(boundary);
    markSeen();                          // dá o "visto" pro time no servidor
    activityModal.hidden = false;
  }
  function closeActivityModal() { activityModal.hidden = true; }

  $("#btn-activity").addEventListener("click", async () => {
    if (!PERFIL) { openPerfilGate(true); return; }
    await loadActivities(); openActivityModal();
  });
  $("#activity-close").addEventListener("click", closeActivityModal);
  activityModal.addEventListener("click", (e) => { if (e.target.id === "activity-modal") closeActivityModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !activityModal.hidden) closeActivityModal(); });

  // ---------------- módulos (Dispatcher / Gestão de Ativos / Agenda / Todo) ----------------
  // Ativos, Agenda e Todo só existem pro perfil Faiston — a LP só acompanha o
  // Dispatcher (fluxos e resultados dos testes).
  let currentModule = "dispatcher";

  function applyModuleVisibility() {
    const isFaiston = PERFIL === "Faiston";
    $("#module-tab-ativos").hidden = !isFaiston;
    $("#module-tab-agenda").hidden = !isFaiston;
    $("#module-tab-todo").hidden = !isFaiston;
    if (!isFaiston && currentModule !== "dispatcher") switchModule("dispatcher");
  }

  function switchModule(mod) {
    currentModule = mod;
    $$(".module-tab").forEach((t) => {
      const on = t.dataset.module === mod;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    $("#module-dispatcher").hidden = mod !== "dispatcher";
    $("#module-ativos").hidden = mod !== "ativos";
    $("#module-agenda").hidden = mod !== "agenda";
    $("#module-todo").hidden = mod !== "todo";
    if (mod === "ativos") loadAjustes();
    if (mod === "agenda") loadAgenda();
    if (mod === "todo") loadTodo();
  }

  $$(".module-tab").forEach((t) => t.addEventListener("click", () => {
    if (t.hidden) return;
    switchModule(t.dataset.module);
  }));

  // ---------------- Agenda (compromissos do time Faiston — semana ou mês) ----------------
  let AGENDA_EVENTS = [];
  const DIA_NOMES = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
  const DIA_NOMES_SEG = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
  const TIPO_META = {
    marco:       { label: "Marco",       color: "var(--f-purple)" },
    relatorio:   { label: "Relatório",   color: "var(--f-blue)" },
    revisao:     { label: "Revisão",     color: "var(--warn)" },
    checkpoint:  { label: "Checkpoint",  color: "var(--f-magenta)" },
    reuniao:     { label: "Reunião",     color: "var(--f-cyan)" },
    teste:       { label: "Teste",       color: "var(--ok)" },
    compromisso: { label: "Compromisso", color: "var(--text-3)" },
  };
  const agendaTipoFiltro = new Set(Object.keys(TIPO_META));

  function startOfWeek(d) {
    const date = new Date(d);
    const day = date.getDay();               // 0 = domingo
    const diff = (day === 0 ? -6 : 1) - day;  // volta pra segunda-feira
    date.setDate(date.getDate() + diff);
    date.setHours(0, 0, 0, 0);
    return date;
  }
  function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r; }
  function startOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }
  function endOfMonth(d) { return new Date(d.getFullYear(), d.getMonth() + 1, 0); }
  function addMonths(d, n) { return new Date(d.getFullYear(), d.getMonth() + n, 1); }
  function isoDate(d) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
  function fmtShort(d) { return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`; }
  function monthGridRange(cursor) {
    const start = startOfWeek(startOfMonth(cursor));
    const end = addDays(startOfWeek(endOfMonth(cursor)), 6);
    return [start, end];
  }

  let agendaView = "mes"; // "mes" | "semana"
  let agendaWeekStart = startOfWeek(new Date());
  let agendaMonthCursor = startOfMonth(new Date());

  async function loadAgenda() {
    const [start, end] = agendaView === "mes" ? monthGridRange(agendaMonthCursor) : [agendaWeekStart, addDays(agendaWeekStart, 6)];
    try {
      AGENDA_EVENTS = await api(`/api/agenda?inicio=${isoDate(start)}&fim=${isoDate(end)}`);
    } catch (e) { AGENDA_EVENTS = []; }
    renderAgenda();
  }

  async function toggleConcluido(id, concluido) {
    const ev = AGENDA_EVENTS.find((e) => e.id === id);
    if (ev) ev.concluido = concluido;
    renderAgenda();
    try {
      await api(`/api/agenda/${id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ concluido }),
      });
    } catch (err) {
      if (ev) ev.concluido = !concluido;
      renderAgenda();
      toast("Erro ao atualizar: " + err.message, true);
    }
  }

  function renderLegend() {
    const legend = $("#agenda-legend");
    legend.innerHTML = Object.entries(TIPO_META).map(([key, meta]) => `
      <button type="button" class="agenda-legend-chip ${agendaTipoFiltro.has(key) ? "is-active" : ""}" data-tipo="${key}" style="--tipo-color:${meta.color}">
        <span class="agenda-legend-dot"></span>${meta.label}
      </button>`).join("");
    $$(".agenda-legend-chip", legend).forEach((b) => b.addEventListener("click", () => {
      const t = b.dataset.tipo;
      if (agendaTipoFiltro.has(t)) agendaTipoFiltro.delete(t); else agendaTipoFiltro.add(t);
      b.classList.toggle("is-active");
      renderAgenda();
    }));
  }

  function eventoCard(ev) {
    const hora = ev.hora_inicio ? esc(ev.hora_inicio) + (ev.hora_fim ? "–" + esc(ev.hora_fim) : "") : "";
    const meta = TIPO_META[ev.tipo] || TIPO_META.compromisso;
    return `<div class="agenda-evento ${ev.concluido ? "is-concluido" : ""}" data-id="${ev.id}" style="--tipo-color:${meta.color}">
      <span class="agenda-evento-check"><input type="checkbox" data-toggle-id="${ev.id}" ${ev.concluido ? "checked" : ""} title="Marcar como concluído"></span>
      <div class="agenda-evento-body">
        ${hora ? `<div class="agenda-evento-hora">${hora}</div>` : ""}
        <div class="agenda-evento-titulo">${esc(ev.titulo)}</div>
      </div>
    </div>`;
  }

  function renderAgenda() {
    if (agendaView === "mes") {
      const label = agendaMonthCursor.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
      $("#agenda-week-label").textContent = label.charAt(0).toUpperCase() + label.slice(1);
      renderMonthGrid();
    } else {
      const end = addDays(agendaWeekStart, 6);
      $("#agenda-week-label").textContent = `${fmtShort(agendaWeekStart)} — ${fmtShort(end)}`;
      renderWeekGrid();
    }
  }

  function renderWeekGrid() {
    const start = agendaWeekStart;
    const todayIso = isoDate(new Date());
    const visible = AGENDA_EVENTS.filter((e) => agendaTipoFiltro.has(e.tipo));
    let html = "";
    for (let i = 0; i < 7; i++) {
      const d = addDays(start, i);
      const iso = isoDate(d);
      const dayEvents = visible.filter((e) => e.data === iso)
        .sort((a, b) => (a.hora_inicio || "").localeCompare(b.hora_inicio || ""));
      html += `<div class="agenda-day ${iso === todayIso ? "is-today" : ""}">
        <button type="button" class="agenda-day-add" data-date="${iso}" aria-label="Adicionar compromisso em ${iso}" title="Adicionar">+</button>
        <div class="agenda-day-head">
          <span class="agenda-day-name">${DIA_NOMES[d.getDay()]}</span>
          <span class="agenda-day-num">${d.getDate()}</span>
        </div>
        <div class="agenda-day-events">${dayEvents.map(eventoCard).join("")}</div>
      </div>`;
    }
    const grid = $("#agenda-grid");
    grid.innerHTML = html;
    grid.hidden = false;
    $("#agenda-grid-month").hidden = true;
    $$(".agenda-day-add", grid).forEach((b) => b.addEventListener("click", () => openEventoModal(null, b.dataset.date)));
    $$(".agenda-evento", grid).forEach((el) => el.addEventListener("click", () => openEventoModal(Number(el.dataset.id))));
    $$(".agenda-evento-check", grid).forEach((el) => el.addEventListener("click", (e) => e.stopPropagation()));
    $$(".agenda-evento-check input", grid).forEach((cb) => cb.addEventListener("change", () => toggleConcluido(Number(cb.dataset.toggleId), cb.checked)));
  }

  function monthEventChip(ev) {
    const meta = TIPO_META[ev.tipo] || TIPO_META.compromisso;
    const hora = ev.hora_inicio ? esc(ev.hora_inicio) + " " : "";
    return `<div class="agenda-month-evento ${ev.concluido ? "is-concluido" : ""}" data-id="${ev.id}" style="--tipo-color:${meta.color}" title="${esc(ev.titulo)}">
      <span class="agenda-month-evento-check"><input type="checkbox" data-toggle-id="${ev.id}" ${ev.concluido ? "checked" : ""} title="Marcar como concluído"></span>
      <span class="agenda-month-evento-title">${hora}${esc(ev.titulo)}</span>
    </div>`;
  }

  function goToWeekOf(iso) {
    agendaWeekStart = startOfWeek(new Date(iso + "T00:00:00"));
    setAgendaView("semana");
  }

  function renderMonthGrid() {
    const [gridStart, gridEnd] = monthGridRange(agendaMonthCursor);
    const totalDias = Math.round((gridEnd - gridStart) / 86400000) + 1;
    const todayIso = isoDate(new Date());
    const curMonth = agendaMonthCursor.getMonth();
    const visible = AGENDA_EVENTS.filter((e) => agendaTipoFiltro.has(e.tipo));
    const MAX_SHOW = 3;

    let html = `<div class="agenda-month-weekdays">${DIA_NOMES_SEG.map((n) => `<div>${n}</div>`).join("")}</div>`;
    html += `<div class="agenda-month-days">`;
    for (let i = 0; i < totalDias; i++) {
      const d = addDays(gridStart, i);
      const iso = isoDate(d);
      const inMonth = d.getMonth() === curMonth;
      const dayEvents = visible.filter((e) => e.data === iso)
        .sort((a, b) => (a.hora_inicio || "").localeCompare(b.hora_inicio || ""));
      const shown = dayEvents.slice(0, MAX_SHOW);
      const extra = dayEvents.length - shown.length;
      html += `<div class="agenda-month-day ${inMonth ? "" : "is-outside"} ${iso === todayIso ? "is-today" : ""}">
        <button type="button" class="agenda-month-day-add" data-date="${iso}" aria-label="Adicionar compromisso em ${iso}" title="Adicionar">+</button>
        <button type="button" class="agenda-month-day-num" data-date="${iso}" title="Ver semana">${d.getDate()}</button>
        <div class="agenda-month-day-events">
          ${shown.map(monthEventChip).join("")}
          ${extra > 0 ? `<button type="button" class="agenda-month-more" data-date="${iso}">+${extra} mais</button>` : ""}
        </div>
      </div>`;
    }
    html += `</div>`;
    const grid = $("#agenda-grid-month");
    grid.innerHTML = html;
    grid.hidden = false;
    $("#agenda-grid").hidden = true;
    $$(".agenda-month-day-add", grid).forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); openEventoModal(null, b.dataset.date); }));
    $$(".agenda-month-day-num", grid).forEach((b) => b.addEventListener("click", () => goToWeekOf(b.dataset.date)));
    $$(".agenda-month-more", grid).forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); goToWeekOf(b.dataset.date); }));
    $$(".agenda-month-evento", grid).forEach((el) => el.addEventListener("click", (e) => { e.stopPropagation(); openEventoModal(Number(el.dataset.id)); }));
    $$(".agenda-month-evento-check", grid).forEach((el) => el.addEventListener("click", (e) => e.stopPropagation()));
    $$(".agenda-month-evento-check input", grid).forEach((cb) => cb.addEventListener("change", () => toggleConcluido(Number(cb.dataset.toggleId), cb.checked)));
  }

  function setAgendaView(view) {
    agendaView = view;
    $$("#agenda-view-toggle .agenda-view-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
    loadAgenda();
  }
  $$("#agenda-view-toggle .agenda-view-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === agendaView);
    b.addEventListener("click", () => setAgendaView(b.dataset.view));
  });

  $("#agenda-prev").addEventListener("click", () => {
    if (agendaView === "mes") agendaMonthCursor = addMonths(agendaMonthCursor, -1);
    else agendaWeekStart = addDays(agendaWeekStart, -7);
    loadAgenda();
  });
  $("#agenda-next").addEventListener("click", () => {
    if (agendaView === "mes") agendaMonthCursor = addMonths(agendaMonthCursor, 1);
    else agendaWeekStart = addDays(agendaWeekStart, 7);
    loadAgenda();
  });
  $("#agenda-today").addEventListener("click", () => {
    agendaWeekStart = startOfWeek(new Date());
    agendaMonthCursor = startOfMonth(new Date());
    loadAgenda();
  });

  renderLegend();

  let editingEventoId = null;
  const eventoModal = $("#evento-modal");
  const eventoForm = $("#evento-form");

  function openEventoModal(id, presetDate) {
    editingEventoId = id || null;
    eventoForm.reset();
    $("#evento-delete").hidden = !id;
    const ev = id ? AGENDA_EVENTS.find((e) => e.id === id) : null;
    $("#evento-modal-title").textContent = id ? "Editar compromisso" : "Novo compromisso";
    if (ev) {
      eventoForm.titulo.value = ev.titulo;
      eventoForm.data.value = ev.data;
      eventoForm.hora_inicio.value = ev.hora_inicio || "";
      eventoForm.hora_fim.value = ev.hora_fim || "";
      eventoForm.descricao.value = ev.descricao || "";
      eventoForm.tipo.value = ev.tipo || "compromisso";
      eventoForm.concluido.checked = !!ev.concluido;
    } else {
      eventoForm.data.value = presetDate || isoDate(new Date());
      eventoForm.tipo.value = "compromisso";
    }
    eventoModal.hidden = false;
  }
  function closeEventoModal() { eventoModal.hidden = true; editingEventoId = null; }

  $("#btn-add-evento").addEventListener("click", () => openEventoModal(null, isoDate(new Date())));
  $("#evento-cancel").addEventListener("click", closeEventoModal);
  $("#evento-modal-close").addEventListener("click", closeEventoModal);
  eventoModal.addEventListener("click", (e) => { if (e.target.id === "evento-modal") closeEventoModal(); });

  eventoForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(eventoForm);
    const titulo = (fd.get("titulo") || "").trim();
    const data = fd.get("data");
    if (!titulo || !data) return;
    const payload = {
      titulo, data,
      hora_inicio: fd.get("hora_inicio") || null,
      hora_fim: fd.get("hora_fim") || null,
      descricao: fd.get("descricao") || "",
      tipo: fd.get("tipo") || "compromisso",
      concluido: fd.get("concluido") === "on",
    };
    try {
      if (editingEventoId) {
        await api(`/api/agenda/${editingEventoId}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
      } else {
        payload.autor = testerName() || undefined;
        await api("/api/agenda", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
      }
      closeEventoModal();
      loadAgenda();
      toast("Compromisso salvo.");
    } catch (err) { toast("Erro ao salvar: " + err.message, true); }
  });

  $("#evento-delete").addEventListener("click", async () => {
    if (!editingEventoId || !confirm("Excluir este compromisso?")) return;
    try {
      await api(`/api/agenda/${editingEventoId}`, { method: "DELETE" });
      closeEventoModal();
      loadAgenda();
      toast("Compromisso excluído.");
    } catch (err) { toast("Erro ao excluir: " + err.message, true); }
  });

  // ---------------- Todo (quadro Kanban do time Faiston) ----------------
  let TODO_TASKS = [];
  const TODO_STATUS_LABEL = { a_fazer: "A Fazer", fazendo: "Fazendo", feito: "Feito" };
  const TODO_STATUS_ORDER = ["a_fazer", "fazendo", "feito"];

  async function loadTodo() {
    try {
      TODO_TASKS = await api("/api/todo");
    } catch (e) { TODO_TASKS = []; }
    renderTodo();
  }

  function tarefaCard(t, status) {
    const idx = TODO_STATUS_ORDER.indexOf(status);
    const canLeft = idx > 0, canRight = idx < TODO_STATUS_ORDER.length - 1;
    return `<div class="kanban-card" data-id="${t.id}">
      <div class="kanban-card-title">${esc(t.titulo)}</div>
      ${t.responsavel ? `<div class="kanban-card-resp">${esc(t.responsavel)}</div>` : ""}
      <div class="kanban-card-actions">
        <button type="button" class="kanban-move" data-dir="left" ${canLeft ? "" : "disabled"}
          title="${canLeft ? "Mover pra " + esc(TODO_STATUS_LABEL[TODO_STATUS_ORDER[idx - 1]]) : ""}">‹</button>
        <button type="button" class="kanban-move" data-dir="right" ${canRight ? "" : "disabled"}
          title="${canRight ? "Mover pra " + esc(TODO_STATUS_LABEL[TODO_STATUS_ORDER[idx + 1]]) : ""}">›</button>
        <button type="button" class="kanban-card-del" aria-label="Excluir tarefa">✕</button>
      </div>
    </div>`;
  }

  function renderTodo() {
    const board = $("#kanban-board");
    TODO_STATUS_ORDER.forEach((status) => {
      const tasks = TODO_TASKS.filter((t) => t.status === status).sort((a, b) => a.posicao - b.posicao);
      $(`#kanban-count-${status}`).textContent = tasks.length;
      $(`#kanban-list-${status}`).innerHTML = tasks.length
        ? tasks.map((t) => tarefaCard(t, status)).join("")
        : '<div class="kanban-empty">Nada por aqui</div>';
    });
    $$(".kanban-card", board).forEach((card) => {
      const id = Number(card.dataset.id);
      $(".kanban-card-title", card).addEventListener("click", () => openTarefaModal(id));
      $$(".kanban-move", card).forEach((btn) => btn.addEventListener("click", () => moveTarefa(id, btn.dataset.dir)));
      $(".kanban-card-del", card).addEventListener("click", () => deleteTarefa(id));
    });
  }

  async function moveTarefa(id, dir) {
    const t = TODO_TASKS.find((x) => x.id === id);
    if (!t) return;
    const idx = TODO_STATUS_ORDER.indexOf(t.status);
    const newIdx = dir === "left" ? idx - 1 : idx + 1;
    if (newIdx < 0 || newIdx >= TODO_STATUS_ORDER.length) return;
    try {
      await api(`/api/todo/${id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: TODO_STATUS_ORDER[newIdx] }),
      });
      loadTodo();
    } catch (e) { toast("Erro ao mover: " + e.message, true); }
  }

  async function deleteTarefa(id) {
    if (!confirm("Excluir esta tarefa?")) return false;
    try {
      await api(`/api/todo/${id}`, { method: "DELETE" });
      loadTodo();
      toast("Tarefa excluída.");
      return true;
    } catch (e) { toast("Erro ao excluir: " + e.message, true); return false; }
  }

  let editingTarefaId = null;
  const tarefaModal = $("#tarefa-modal");
  const tarefaForm = $("#tarefa-form");

  function openTarefaModal(id) {
    editingTarefaId = id || null;
    tarefaForm.reset();
    $("#tarefa-delete").hidden = !id;
    const t = id ? TODO_TASKS.find((x) => x.id === id) : null;
    $("#tarefa-modal-title").textContent = id ? "Editar tarefa" : "Nova tarefa";
    if (t) {
      tarefaForm.titulo.value = t.titulo;
      tarefaForm.responsavel.value = t.responsavel || "";
      tarefaForm.descricao.value = t.descricao || "";
    }
    tarefaModal.hidden = false;
  }
  function closeTarefaModal() { tarefaModal.hidden = true; editingTarefaId = null; }

  $("#btn-add-tarefa").addEventListener("click", () => openTarefaModal(null));
  $("#tarefa-cancel").addEventListener("click", closeTarefaModal);
  $("#tarefa-modal-close").addEventListener("click", closeTarefaModal);
  tarefaModal.addEventListener("click", (e) => { if (e.target.id === "tarefa-modal") closeTarefaModal(); });

  tarefaForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(tarefaForm);
    const titulo = (fd.get("titulo") || "").trim();
    if (!titulo) return;
    const payload = {
      titulo,
      responsavel: fd.get("responsavel") || null,
      descricao: fd.get("descricao") || "",
    };
    try {
      if (editingTarefaId) {
        await api(`/api/todo/${editingTarefaId}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
      } else {
        payload.autor = testerName() || undefined;
        await api("/api/todo", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
      }
      closeTarefaModal();
      loadTodo();
      toast("Tarefa salva.");
    } catch (err) { toast("Erro ao salvar: " + err.message, true); }
  });

  $("#tarefa-delete").addEventListener("click", async () => {
    if (!editingTarefaId) return;
    const ok = await deleteTarefa(editingTarefaId);
    if (ok) closeTarefaModal();
  });

  // ---------------- Gestão de Ativos — ajustes (v2 e as próximas levas) ----------------
  // Cada ajuste é um "como está hoje / como deve ser" classificado como Bug ou
  // Melhoria. A versão (v2, v3…) vem dos próprios dados: cadastrou um item numa
  // versão que ainda não existia, a aba dela aparece sozinha aqui.
  let AJUSTES = [];
  let ajusteVersao = "";                         // "" enquanto não carregou nada
  const ajusteFiltros = { tipo: "", status: "" };

  const AJUSTE_STATUS = [
    { key: "levantado",       label: "Levantado",         cls: "st-levantado" },
    { key: "analise",         label: "Em análise",        cls: "st-analise" },
    { key: "desenvolvimento", label: "Em desenvolvimento", cls: "st-dev" },
    { key: "entregue",        label: "Entregue",           cls: "st-entregue" },
    { key: "validado",        label: "Validado",           cls: "st-validado" },
    { key: "descartado",      label: "Descartado",         cls: "st-descartado" },
  ];
  const AJUSTE_STATUS_META = Object.fromEntries(AJUSTE_STATUS.map((s) => [s.key, s]));
  // o que ainda dá trabalho — usado no contador da aba e no "em aberto" do resumo
  const AJUSTE_ABERTO = new Set(["levantado", "analise", "desenvolvimento", "entregue"]);

  // a lista sai por prioridade: Alta primeiro, "A definir" por último. O número
  // do item não muda — ele é a identidade do ajuste ("o ajuste 4"), não a ordem.
  const AJUSTE_PRIORIDADE_ORDEM = { "Alta": 0, "Média": 1, "Baixa": 2, "A definir": 3 };
  const prioridadeRank = (p) => (p in AJUSTE_PRIORIDADE_ORDEM ? AJUSTE_PRIORIDADE_ORDEM[p] : 3);
  const AJUSTE_PRIORIDADE_CLASS = { "Alta": "p-alta", "Média": "p-media", "Baixa": "p-baixa" };
  const prioridadeCls = (p) => AJUSTE_PRIORIDADE_CLASS[p] || "p-definir";

  // v10 depois de v9: ordena pelo número da versão, não pelo texto
  function versaoRank(v) {
    const n = parseInt(String(v).replace(/\D/g, ""), 10);
    return isNaN(n) ? 0 : n;
  }

  async function loadAjustes() {
    try {
      AJUSTES = await api("/api/ativos/ajustes");
    } catch (e) {
      AJUSTES = [];
      toast("Erro ao carregar ajustes: " + e.message, true);
    }
    const versoes = versoesDisponiveis();
    if (!versoes.includes(ajusteVersao)) ajusteVersao = versoes[0] || "v2";
    renderAjustes();
  }

  function versoesDisponiveis() {
    return Array.from(new Set(AJUSTES.map((a) => a.versao))).sort((a, b) => versaoRank(b) - versaoRank(a));
  }

  function ajustesDaVersao() {
    return AJUSTES.filter((a) => a.versao === ajusteVersao);
  }

  function renderAjustes() {
    renderAjusteVersoes();
    renderAjusteStats();
    renderAjusteStatusChips();
    renderAjusteList();
    atualizaContadorAba();
    // datalist do modal: as versões que já existem, pra não digitar errado
    $("#ajuste-versao-opts").innerHTML = versoesDisponiveis().map((v) => `<option value="${esc(v)}">`).join("");
  }

  function renderAjusteVersoes() {
    const versoes = versoesDisponiveis();
    const nav = $("#ajustes-versoes");
    if (!versoes.length) { nav.innerHTML = ""; return; }
    nav.innerHTML = versoes.map((v) => {
      const itens = AJUSTES.filter((a) => a.versao === v);
      const abertos = itens.filter((a) => AJUSTE_ABERTO.has(a.status)).length;
      return `<button type="button" class="ajuste-versao${v === ajusteVersao ? " active" : ""}" data-versao="${esc(v)}">
        <span class="ajuste-versao-name">Ajustes ${esc(v)}</span>
        <span class="ajuste-versao-sub">${itens.length} ${itens.length === 1 ? "item" : "itens"} · ${abertos} em aberto</span>
      </button>`;
    }).join("");
    $$(".ajuste-versao", nav).forEach((b) => b.addEventListener("click", () => {
      ajusteVersao = b.dataset.versao;
      renderAjustes();
    }));
  }

  function renderAjusteStats() {
    const itens = ajustesDaVersao();
    const bugs = itens.filter((a) => a.tipo === "Bug").length;
    const melhorias = itens.filter((a) => a.tipo === "Melhoria").length;
    const abertos = itens.filter((a) => AJUSTE_ABERTO.has(a.status)).length;
    const prontos = itens.filter((a) => a.status === "validado").length;
    $("#ajustes-stats").innerHTML = `
      <div class="stat"><span class="stat-n">${itens.length}</span><span class="stat-l">Ajustes</span></div>
      <div class="stat bad"><span class="stat-n">${bugs}</span><span class="stat-l">Bugs</span></div>
      <div class="stat"><span class="stat-n">${melhorias}</span><span class="stat-l">Melhorias</span></div>
      <div class="stat warn"><span class="stat-n">${abertos}</span><span class="stat-l">Em aberto</span></div>
      <div class="stat ok"><span class="stat-n">${prontos}</span><span class="stat-l">Validados</span></div>`;
  }

  function renderAjusteStatusChips() {
    const itens = ajustesDaVersao();
    const box = $("#ajustes-chips-status");
    const chips = [`<button type="button" class="chip${ajusteFiltros.status ? "" : " active"}" data-status="">Todas</button>`];
    AJUSTE_STATUS.forEach((st) => {
      const n = itens.filter((a) => a.status === st.key).length;
      if (!n && ajusteFiltros.status !== st.key) return;   // só mostra situação que existe na versão
      chips.push(`<button type="button" class="chip${ajusteFiltros.status === st.key ? " active" : ""}" data-status="${st.key}">${esc(st.label)} <b>${n}</b></button>`);
    });
    box.innerHTML = chips.join("");
    $$(".chip", box).forEach((c) => c.addEventListener("click", () => {
      ajusteFiltros.status = c.dataset.status;
      renderAjustes();
    }));
  }

  function ajusteCard(a) {
    const tipoCls = a.tipo === "Bug" ? "t-bug" : "t-melhoria";
    const st = AJUSTE_STATUS_META[a.status] || AJUSTE_STATUS[0];
    const opts = AJUSTE_STATUS.map((s) =>
      `<option value="${s.key}"${s.key === a.status ? " selected" : ""}>${esc(s.label)}</option>`).join("");
    return `<article class="ajuste-item ${tipoCls} ${st.cls}" data-id="${a.id}">
      <header class="ajuste-item-head">
        <span class="ajuste-num">${String(a.numero || 0).padStart(2, "0")}</span>
        <div class="ajuste-item-copy">
          <h3>${esc(a.titulo)}</h3>
          <div class="ajuste-tags">
            <span class="ajuste-tag ${tipoCls}">${esc(a.tipo)}</span>
            ${a.area ? `<span class="ajuste-tag t-area">${esc(a.area)}</span>` : ""}
            <span class="ajuste-tag t-prio ${prioridadeCls(a.prioridade)}">${esc(a.prioridade)}</span>
            ${a.responsavel ? `<span class="ajuste-tag t-resp">${esc(a.responsavel)}</span>` : ""}
          </div>
        </div>
        <select class="ajuste-status ${st.cls}" title="Situação do ajuste">${opts}</select>
        <button type="button" class="ajuste-edit" aria-label="Editar ajuste" title="Editar">✎</button>
      </header>
      <div class="ajuste-cols">
        <div class="ajuste-col col-atual">
          <span class="ajuste-col-label">Como está hoje</span>
          <p>${esc(a.atual) || "<span class=\"ajuste-vazio\">—</span>"}</p>
        </div>
        <div class="ajuste-col col-esperado">
          <span class="ajuste-col-label">Como deve ser</span>
          <p>${esc(a.esperado) || "<span class=\"ajuste-vazio\">—</span>"}</p>
        </div>
      </div>
      ${a.observacao ? `<div class="ajuste-obs"><b>Obs.</b> ${esc(a.observacao)}</div>` : ""}
    </article>`;
  }

  function renderAjusteList() {
    const lista = $("#ajustes-list");
    const itens = ajustesDaVersao()
      .filter((a) => !ajusteFiltros.tipo || a.tipo === ajusteFiltros.tipo)
      .filter((a) => !ajusteFiltros.status || a.status === ajusteFiltros.status)
      .sort((a, b) => prioridadeRank(a.prioridade) - prioridadeRank(b.prioridade)
                      || (a.numero || 0) - (b.numero || 0) || a.id - b.id);

    const semNada = !ajustesDaVersao().length;
    $("#ajustes-empty").hidden = !semNada;
    if (semNada) { lista.innerHTML = ""; return; }

    lista.innerHTML = itens.length
      ? itens.map(ajusteCard).join("")
      : '<div class="ajustes-nofilter">Nenhum ajuste com esses filtros.</div>';

    $$(".ajuste-item", lista).forEach((card) => {
      const id = Number(card.dataset.id);
      $(".ajuste-edit", card).addEventListener("click", () => openAjusteModal(id));
      $(".ajuste-item-copy h3", card).addEventListener("click", () => openAjusteModal(id));
      $(".ajuste-status", card).addEventListener("change", (e) => setAjusteStatus(id, e.target.value));
    });
  }

  function atualizaContadorAba() {
    const badge = $("#module-tab-ativos-count");
    if (!badge) return;
    const abertos = AJUSTES.filter((a) => AJUSTE_ABERTO.has(a.status)).length;
    badge.textContent = abertos;
    badge.hidden = !abertos;
  }

  async function setAjusteStatus(id, status) {
    try {
      await api(`/api/ativos/ajustes/${id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const a = AJUSTES.find((x) => x.id === id);
      if (a) a.status = status;
      renderAjustes();
      toast("Situação atualizada.");
    } catch (e) { toast("Erro ao atualizar: " + e.message, true); }
  }

  let editingAjusteId = null;
  const ajusteModal = $("#ajuste-modal");
  const ajusteForm = $("#ajuste-form");

  function openAjusteModal(id) {
    editingAjusteId = id || null;
    ajusteForm.reset();
    const a = id ? AJUSTES.find((x) => x.id === id) : null;
    $("#ajuste-modal-title").textContent = id ? "Editar ajuste" : "Novo ajuste";
    $("#ajuste-modal-code").textContent = a
      ? `${esc(a.versao)} · item ${String(a.numero || 0).padStart(2, "0")}`
      : `${esc(ajusteVersao || "v2")} · novo item`;
    $("#ajuste-delete").hidden = !id;
    if (a) {
      ajusteForm.titulo.value = a.titulo;
      ajusteForm.tipo.value = a.tipo;
      ajusteForm.versao.value = a.versao;
      ajusteForm.prioridade.value = a.prioridade;
      ajusteForm.area.value = a.area || "";
      ajusteForm.status.value = a.status;
      ajusteForm.responsavel.value = a.responsavel || "";
      ajusteForm.atual.value = a.atual || "";
      ajusteForm.esperado.value = a.esperado || "";
      ajusteForm.observacao.value = a.observacao || "";
    } else {
      ajusteForm.versao.value = ajusteVersao || "v2";
    }
    ajusteModal.hidden = false;
  }
  function closeAjusteModal() { ajusteModal.hidden = true; editingAjusteId = null; }

  $("#btn-add-ajuste").addEventListener("click", () => openAjusteModal(null));
  $("#btn-add-ajuste-vazio").addEventListener("click", () => openAjusteModal(null));
  $("#ajuste-cancel").addEventListener("click", closeAjusteModal);
  $("#ajuste-modal-close").addEventListener("click", closeAjusteModal);
  ajusteModal.addEventListener("click", (e) => { if (e.target.id === "ajuste-modal") closeAjusteModal(); });

  $$("#ajustes-chips-tipo .chip").forEach((c) => c.addEventListener("click", () => {
    ajusteFiltros.tipo = c.dataset.tipo;
    $$("#ajustes-chips-tipo .chip").forEach((o) => o.classList.toggle("active", o === c));
    renderAjusteList();
  }));

  ajusteForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(ajusteForm);
    const titulo = (fd.get("titulo") || "").trim();
    if (!titulo) return;
    const payload = {
      titulo,
      tipo: fd.get("tipo"),
      versao: (fd.get("versao") || "").trim() || ajusteVersao || "v2",
      prioridade: fd.get("prioridade"),
      area: fd.get("area") || null,
      status: fd.get("status"),
      responsavel: fd.get("responsavel") || null,
      atual: fd.get("atual") || "",
      esperado: fd.get("esperado") || "",
      observacao: fd.get("observacao") || "",
    };
    try {
      if (editingAjusteId) {
        await api(`/api/ativos/ajustes/${editingAjusteId}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        const criado = await api("/api/ativos/ajustes", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...payload, autor: testerName() || null }),
        });
        // cadastrou numa versão nova: já pula pra ela
        ajusteVersao = criado.versao;
      }
      closeAjusteModal();
      await loadAjustes();
      toast("Ajuste salvo.");
    } catch (err) { toast("Erro ao salvar: " + err.message, true); }
  });

  $("#ajuste-delete").addEventListener("click", async () => {
    if (!editingAjusteId) return;
    if (!confirm("Excluir este ajuste?")) return;
    try {
      await api(`/api/ativos/ajustes/${editingAjusteId}`, { method: "DELETE" });
      closeAjusteModal();
      await loadAjustes();
      toast("Ajuste excluído.");
    } catch (e) { toast("Erro ao excluir: " + e.message, true); }
  });

  // na entrada: aplica o chip e, se ninguém escolheu ainda, força a escolha do perfil
  applyPerfilChip();
  applyModuleVisibility();
  if (!PERFIL) openPerfilGate(false);

  // ---------------- tester name ----------------
  const testerInput = $("#input-tester");
  testerInput.value = localStorage.getItem(TESTER_KEY) || "";
  testerInput.addEventListener("change", () => localStorage.setItem(TESTER_KEY, testerInput.value.trim()));

  // ---------------- boot ----------------
  loadActivities();
  loadCases().catch((e) => {
    $("#cases-loading").textContent = "Erro ao carregar casos: " + e.message;
  });
  loadNotes();
  loadSituacoes();
  loadAjustes();
})();
