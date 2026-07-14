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
