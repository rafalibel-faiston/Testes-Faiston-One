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
  }
  $("#f-busca").addEventListener("input", applyFilters);

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
    const total = flowCases.length;
    const executado = total - counts["Não testado"];
    const pct = total ? Math.round((executado / total) * 100) : 0;
    $("#hero-pct").textContent = pct + "%";
    $("#pbar-fill").style.width = pct + "%";
    updatePresentCount();
  }

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
    loadNotes();
    if (typeof onFlowChangedForDiagrams === "function") onFlowChangedForDiagrams();
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
  // Lista solta por fluxo, independente de qualquer caso de teste — pra
  // anotar na hora um ponto (bug, dúvida, decisão pendente) e levar pra reunião.
  let NOTES = [];
  const notesModal = $("#notes-modal");

  async function loadNotes() {
    try {
      NOTES = await api(`/api/notas?fluxo=${encodeURIComponent(currentFlow)}`);
    } catch (e) {
      NOTES = [];
    }
    updateNotesCount();
    if (!notesModal.hidden) renderNotesList();
  }

  function updateNotesCount() {
    const open = NOTES.filter((n) => !n.resolvido).length;
    const el = $("#notes-count");
    if (el) el.textContent = open;
  }

  function noteItem(n) {
    return `<div class="note-item ${n.resolvido ? "resolvido" : ""}" data-id="${n.id}">
      <div class="note-head">
        <input type="checkbox" class="note-check" ${n.resolvido ? "checked" : ""} title="Marcar como discutido">
        ${n.estagio ? `<span class="tag note-stage">${esc(n.estagio)}</span>` : ""}
        <button type="button" class="note-del" title="Excluir ponto" aria-label="Excluir">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
      <div class="note-text">${esc(n.texto)}</div>
      <div class="note-meta">${n.autor ? esc(n.autor) + " · " : ""}${fmtWhen(n.created_at)}</div>
    </div>`;
  }

  function renderNotesList() {
    const el = $("#notes-list");
    if (!NOTES.length) {
      el.innerHTML = `<div class="notes-empty">Nenhum ponto anotado ainda neste fluxo.</div>`;
      return;
    }
    el.innerHTML = NOTES.map(noteItem).join("");
    $$(".note-check", el).forEach((chk) => {
      chk.addEventListener("change", () => toggleNote(chk.closest(".note-item").dataset.id, chk.checked));
    });
    $$(".note-del", el).forEach((btn) => {
      btn.addEventListener("click", () => deleteNote(btn.closest(".note-item").dataset.id));
    });
  }

  async function toggleNote(id, resolvido) {
    try {
      const updated = await api(`/api/notas/${id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resolvido }),
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

  function openNotesModal() {
    $("#notes-flow-label").textContent = "Fluxo " + currentFlow;
    renderNotesList();
    notesModal.hidden = false;
    setTimeout(() => { try { $("#notes-input").focus(); } catch (e) {} }, 30);
  }
  function closeNotesModal() { notesModal.hidden = true; }

  $("#btn-notes").addEventListener("click", openNotesModal);
  $("#notes-close").addEventListener("click", closeNotesModal);
  notesModal.addEventListener("click", (e) => { if (e.target.id === "notes-modal") closeNotesModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !notesModal.hidden) closeNotesModal(); });

  $("#notes-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#notes-input");
    const estagioInput = $("#notes-estagio");
    const texto = input.value.trim();
    if (!texto) return;
    try {
      const created = await api("/api/notas", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fluxo: currentFlow, texto, autor: testerName() || undefined,
          estagio: estagioInput.value.trim() || undefined,
        }),
      });
      NOTES.push(created);
      input.value = "";
      estagioInput.value = "";
      renderNotesList();
      updateNotesCount();
    } catch (err) { toast("Erro ao salvar ponto: " + err.message, true); }
  });

  // ---------------- fluxos (diagramas Mermaid) ----------------
  let currentView = "testes";        // "testes" | "fluxos"
  let DIAGRAMS = [];
  let diagramsLoaded = false;
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
    if (view === "fluxos") loadDiagrams();
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
    return `<article class="diagram kind-${esc(d.kind)}" data-id="${d.id}">
      <div class="diagram-head">
        <span class="diagram-kind">${esc(KIND_LABEL[d.kind] || d.kind)}</span>
        <span class="diagram-title">${esc(d.titulo)}</span>
        <span class="diagram-actions">
          <button type="button" class="case-icon-btn diagram-edit" title="Editar diagrama" aria-label="Editar">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button type="button" class="case-icon-btn danger diagram-del" title="Excluir diagrama" aria-label="Excluir">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </span>
      </div>
      ${d.descricao ? `<div class="diagram-desc">${esc(d.descricao)}</div>` : ""}
      <div class="diagram-canvas" data-canvas="${d.id}"><div class="diagram-preview-empty">Renderizando…</div></div>
      <div class="diagram-meta-foot">${d.atualizado_por ? `Atualizado por <span class="who">${esc(d.atualizado_por)}</span> · ` : ""}${fmtWhen(d.updated_at)}${d.seeded ? " · <span class=\"who\">modelo inicial</span>" : ""}</div>
    </article>`;
  }

  function renderDiagrams() {
    const list = DIAGRAMS.filter((d) => (d.fluxo || "C") === currentFlow)
      .sort((a, b) => (a.kind < b.kind ? -1 : a.kind > b.kind ? 1 : (a.ordem || 0) - (b.ordem || 0)));
    const emptyEl = $("#diagrams-empty");
    const wrap = $("#diagrams");
    if (!list.length) {
      wrap.innerHTML = "";
      emptyEl.hidden = false;
      return;
    }
    emptyEl.hidden = true;
    wrap.innerHTML = list.map(diagramCard).join("");
    list.forEach((d) => {
      const canvas = wrap.querySelector(`.diagram-canvas[data-canvas="${d.id}"]`);
      if (canvas) renderMermaidInto(canvas, d.mermaid);
    });
    $$(".diagram-edit", wrap).forEach((btn) => {
      btn.addEventListener("click", () => openDiagramModal("edit", btn.closest(".diagram").dataset.id));
    });
    $$(".diagram-del", wrap).forEach((btn) => {
      btn.addEventListener("click", () => deleteDiagram(btn.closest(".diagram").dataset.id));
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

  function newNodeId() {
    let id;
    do { id = "n" + (++builder.nSeq); } while (builder.nodes.some((n) => n.id === id));
    return id;
  }

  // --- gerar código Mermaid a partir do estado ---
  function cleanLabel(s) { return (s || "").replace(/["|]/g, " ").replace(/\s+/g, " ").trim(); }
  function generateMermaid(s) {
    const lines = ["flowchart " + (s.dir || "TD")];
    s.nodes.forEach((n) => {
      const label = cleanLabel(n.label) || n.id;
      lines.push(n.shape === "decision" ? `    ${n.id}{"${label}"}` : `    ${n.id}["${label}"]`);
    });
    s.edges.forEach((e) => {
      if (!e.from || !e.to) return;
      const lbl = cleanLabel(e.label);
      if (e.dotted) lines.push(lbl ? `    ${e.from} -. ${lbl} .-> ${e.to}` : `    ${e.from} -.-> ${e.to}`);
      else lines.push(lbl ? `    ${e.from} -->|${lbl}| ${e.to}` : `    ${e.from} --> ${e.to}`);
    });
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
    // registra rótulo/forma e devolve a linha só com os ids (ex.: A --> B)
    const extractNodes = (line) => line.replace(/([A-Za-z0-9_]+)\s*(\[|\{|\()\s*"?(.*?)"?\s*(\]|\}|\))/g, (full, id, open, label) => {
      const n = ensure(id);
      n.label = label;
      n.shape = open === "{" ? "decision" : "step";
      return id;
    });
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
      <div class="builder-row ${n.shape === "decision" ? "is-decision" : ""}" data-id="${n.id}">
        <span class="b-num">${i + 1}</span>
        <input type="text" class="b-label" value="${esc(n.label)}" placeholder="texto da etapa">
        <select class="b-shape">
          <option value="step" ${n.shape === "step" ? "selected" : ""}>Etapa</option>
          <option value="decision" ${n.shape === "decision" ? "selected" : ""}>Decisão</option>
        </select>
        <button type="button" class="builder-del" title="Remover etapa" aria-label="Remover">×</button>
      </div>`).join("");
    $$(".builder-row", el).forEach((row) => {
      const id = row.dataset.id;
      const node = builder.nodes.find((n) => n.id === id);
      row.querySelector(".b-label").addEventListener("input", (ev) => { node.label = ev.target.value; scheduleSync(); });
      row.querySelector(".b-label").addEventListener("change", () => renderEdges());
      row.querySelector(".b-shape").addEventListener("change", (ev) => { node.shape = ev.target.value; row.classList.toggle("is-decision", ev.target.value === "decision"); scheduleSync(); });
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
      renderMermaidInto($("#diagram-preview"), code);
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
    renderMermaidInto($("#diagram-preview"), code);
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
    setBuilderState(state);
    diagramModal.hidden = false;
    setTimeout(() => { try { diagramForm.titulo.focus(); } catch (e) {} }, 30);
  }
  function closeDiagramModal() { diagramModal.hidden = true; editingDiagramId = null; }

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
        toast("Diagrama atualizado");
      } else {
        await api("/api/diagramas", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
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
    previewTimer = setTimeout(() => renderMermaidInto($("#diagram-preview"), diagramSource.value), 300);
  });
  $("#diagram-close").addEventListener("click", closeDiagramModal);
  $("#diagram-cancel").addEventListener("click", closeDiagramModal);
  diagramModal.addEventListener("click", (e) => { if (e.target.id === "diagram-modal") closeDiagramModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !diagramModal.hidden) closeDiagramModal(); });
  // título/badge iniciais coerentes com o fluxo atual
  onFlowChangedForDiagrams();

  // ---------------- tester name ----------------
  const testerInput = $("#input-tester");
  testerInput.value = localStorage.getItem(TESTER_KEY) || "";
  testerInput.addEventListener("change", () => localStorage.setItem(TESTER_KEY, testerInput.value.trim()));

  // ---------------- boot ----------------
  loadCases().catch((e) => {
    $("#cases-loading").textContent = "Erro ao carregar casos: " + e.message;
  });
  loadNotes();
})();
