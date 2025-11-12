/* ==========================
   Helper utilities
   ========================== */
function q(id){ return document.getElementById(id); }

function val(v, fallback = "Not provided") {
  if (v === null || v === undefined) return fallback;
  if (Array.isArray(v)) return v.length ? v.join(", ") : fallback;
  if (typeof v === "object") return JSON.stringify(v);
  const s = String(v).trim();
  return s.length ? s : fallback;
}

function addressFrom(md){
  if (md.full_address) return md.full_address;
  const parts = [md.street, md.city, md.state, md.zip_code].filter(Boolean);
  return parts.length ? parts.join(", ") : "Not provided";
}
function telHref(phone){ if(!phone) return null; const d=String(phone).replace(/[^+\d]/g,""); return d?`tel:${d}`:null; }
function mapsHref(addr){ if(!addr||addr==="Not provided") return null; return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(addr)}`; }
function icon(name, color="%2354618c"){
  const m={phone:`<svg class="ico" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="${color}"><path d="M6.62 10.79a15.91 15.91 0 006.59 6.59l2.2-2.2a1 1 0 011.01-.24 12.36 12.36 0 003.88.62 1 1 0 011 1V20a1 1 0 01-1 1A17 17 0 013 4a1 1 0 011-1h3.44a1 1 0 011 1 12.36 12.36 0 00.62 3.88 1 1 0 01-.24 1.01l-2.2 2.2z"/></svg>`,
           globe:`<svg class="ico" xmlns="http://www.w3.org/2000/svg" fill="${color}" viewBox="0 0 24 24"><path d="M12 2a10 10 0 1010 10A10.011 10.011 0 0012 2zm1 17.93V20h-2v-.07A8.014 8.014 0 014.07 13H4v-2h.07A8.014 8.014 0 0111 4.07V4h2v.07A8.014 8.014 0 0119.93 11H20v2h-.07A8.014 8.014 0 0113 19.93z"/></svg>`,
           map:`<svg class="ico" xmlns="http://www.w3.org/2000/svg" fill="${color}" viewBox="0 0 24 24"><path d="M15 4l-6 2-6-2v16l6 2 6-2 6 2V6z"/></svg>`,
           mail:`<svg class="ico" xmlns="http://www.w3.org/2000/svg" fill="${color}" viewBox="0 0 24 24"><path d="M20 4H4a2 2 0 00-2 2v1l10 6 10-6V6a2 2 0 00-2-2zm0 6.236l-8 4.8-8-4.8V18a2 2 0 002 2h12a2 2 0 002-2z"/></svg>`,
           copy:`<svg class="ico" xmlns="http://www.w3.org/2000/svg" fill="${color}" viewBox="0 0 24 24"><path d="M16 1H4a2 2 0 00-2 2v12h2V3h12z"/><path d="M20 5H8a2 2 0 00-2 2v14h14a2 2 0 002-2V7a2 2 0 00-2-2z"/></svg>`};
  return m[name]||"";
}
function showToast(msg){ const el=q("toast"); el.textContent=msg; el.classList.add("show"); setTimeout(()=>el.classList.remove("show"),1600); }

function slugToTitle(slug){
  if(!slug) return "Recommended Resources";
  return slug.split("-").map(part=>part ? part[0].toUpperCase()+part.slice(1) : "").join(" ").trim();
}

const resourceIndex = {};

const carouselState = {
  slides: [],
  themes: [],
  currentSlide: 0
};

let carouselControlsBound = false;

function resourceId(h){
  const md = h?.metadata || {};
  const identifier = h?.id ?? h?.service_id ?? md.resource_id ?? md.id ?? "";
  return identifier !== undefined && identifier !== null ? String(identifier) : "";
}

function setPromptOverlay(active){
  document.body.classList.toggle("prompt-overlay-active", !!active);
  syncPromptSpacer();
}

function syncPromptSpacer(){
  const panel = q("prompt-panel");
  const spacer = q("prompt-spacer");
  if(!panel || !spacer) return;
  if(document.body.classList.contains("prompt-overlay-active")){
    spacer.style.height = `${panel.offsetHeight + 24}px`;
  }else{
    spacer.style.height = "0px";
  }
}

function scrollToResults(){
  const anchor = q("results-anchor") || q("results");
  if(!anchor) return;
  anchor.scrollIntoView({ behavior: "smooth", block: "start" });
}

function clearCarousel(){
  const track = q("carousel-track");
  if(track){
    track.innerHTML = "";
    track.style.transform = "translateX(0%)";
  }
  const meta = q("carousel-meta");
  if(meta){
    meta.textContent = "";
    meta.hidden = true;
  }
  const themesSummary = q("themes-summary");
  if(themesSummary) themesSummary.hidden = true;
  const themesList = q("themes-list");
  if(themesList) themesList.innerHTML = "";
  const carousel = q("results-carousel");
  if(carousel) carousel.hidden = true;
  const prev = q("carousel-prev");
  const next = q("carousel-next");
  if(prev) prev.disabled = true;
  if(next) next.disabled = true;
  carouselState.slides = [];
  carouselState.themes = [];
  carouselState.currentSlide = 0;
}

function ensureCarouselControls(){
  if(carouselControlsBound) return;
  const prev = q("carousel-prev");
  const next = q("carousel-next");
  const themeList = q("themes-list");
  prev?.addEventListener("click", ()=> moveSlide(-1));
  next?.addEventListener("click", ()=> moveSlide(1));
  themeList?.addEventListener("click", (event)=>{
    const target = event.target.closest?.(".theme-chip");
    if(!target) return;
    const idx = Number(target.getAttribute("data-theme-index"));
    if(Number.isNaN(idx)) return;
    setActiveTheme(idx, { scroll: true });
  });
  carouselControlsBound = true;
}

function moveSlide(delta){
  if(!carouselState.slides.length) return;
  const nextIndex = carouselState.currentSlide + delta;
  setActiveSlide(nextIndex, { scroll: false });
}

function setActiveTheme(themeIndex, options = {}){
  const theme = carouselState.themes[themeIndex];
  if(!theme) return;
  const target = theme.start ?? 0;
  setActiveSlide(target, options);
}

function setActiveSlide(index, options = {}){
  if(!carouselState.slides.length) return;
  const clamped = Math.max(0, Math.min(index, carouselState.slides.length - 1));
  carouselState.currentSlide = clamped;
  updateCarouselUI();
  if(options.scroll){
    scrollToResults();
  }
  if(options.highlight){
    highlightSlide(clamped);
  }
}

function highlightSlide(slideIndex){
  const slideEl = document.querySelector(`.carousel-slide[data-slide-index="${slideIndex}"] .result-card`);
  if(!slideEl) return;
  slideEl.classList.add("highlighted");
  setTimeout(()=> slideEl.classList.remove("highlighted"), 1600);
}

function updateCarouselUI(){
  const track = q("carousel-track");
  const slides = track?.querySelectorAll?.(".carousel-slide") || [];
  if(!slides.length) return;
  const { currentSlide, themes } = carouselState;
  const offset = currentSlide * -100;
  if(track){
    track.style.transform = `translateX(${offset}%)`;
  }

  slides.forEach((slide, idx)=>{
    const isActive = idx === currentSlide;
    slide.classList.toggle("is-active", isActive);
    slide.setAttribute("aria-hidden", isActive ? "false" : "true");
  });

  const prev = q("carousel-prev");
  const next = q("carousel-next");
  if(prev) prev.disabled = currentSlide === 0;
  if(next) next.disabled = currentSlide === carouselState.slides.length - 1;

  const activeSlide = carouselState.slides[currentSlide];
  if(!activeSlide) return;
  const activeThemeIndex = activeSlide.themeIndex;
  carouselState.currentSlide = currentSlide;

  const themeList = q("themes-list");
  if(themeList){
    themeList.querySelectorAll(".theme-chip").forEach(chip=>{
      const idx = Number(chip.getAttribute("data-theme-index"));
      const isActive = idx === activeThemeIndex;
      chip.classList.toggle("active", isActive);
      chip.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
  }

  const theme = themes[activeThemeIndex];
  if(!theme) return;
  const meta = q("carousel-meta");
  if(meta){
    const withinTheme = currentSlide - (theme.start ?? 0) + 1;
    meta.hidden = false;
    meta.textContent = `${theme.label}: result ${withinTheme} of ${theme.count} • ${currentSlide + 1} of ${carouselState.slides.length} overall`;
  }
}

function resetResourceIndex(){
  Object.keys(resourceIndex).forEach(key=>{ delete resourceIndex[key]; });
}

function updateResourceIndex(){
  resetResourceIndex();
  document.querySelectorAll(".carousel-slide").forEach(slide=>{
    const card = slide.querySelector(".result-card[data-id]");
    if(!card) return;
    const id = card.getAttribute("data-id");
    if(!id) return;
    const title = card.querySelector(".card-title");
    const slideIndex = Number(slide.getAttribute("data-slide-index"));
    const themeIndex = Number(slide.getAttribute("data-theme-index"));
    resourceIndex[id] = {
      name: (title?.textContent || `Resource ${id}`).trim(),
      element: slide,
      slideIndex: Number.isNaN(slideIndex) ? 0 : slideIndex,
      themeIndex: Number.isNaN(themeIndex) ? 0 : themeIndex
    };
  });
}

function focusResourceById(id){
  const info = resourceIndex[id];
  if(!info) return;
  const slideIndex = info.slideIndex ?? 0;
  setActiveSlide(slideIndex, { scroll: true, highlight: true });
}

function escapeHTML(str=""){
  return String(str).replace(/[&<>"']/g, ch=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[ch]);
}

function attachCitationHandlers(){
  document.querySelectorAll(".cite-link").forEach(btn=>{
    btn.addEventListener("click", ()=>{
      const id = btn.getAttribute("data-id");
      if(!id) return;
      focusResourceById(id);
    });
  });
}

function renderActionPlan(text){
  const section=q("action-plan");
  const body=q("action-plan-body");
  if(!section || !body) return;
  const value=(text||"").trim();
  if(value){
    const escaped = escapeHTML(value);
    const withCites = escaped.replace(/\[cite:\s*([^\]\s]+)\]/g, (_, id)=>{
      const label = resourceIndex[id]?.name || `Resource ${id}`;
      return `<button type="button" class="cite-link" data-id="${id}">[${escapeHTML(label)}]</button>`;
    });
    const paragraphs = withCites.split(/\n{2,}/).map(p=>`<p>${p.replace(/\n/g,"<br>")}</p>`).join("");
    section.hidden=false;
    body.innerHTML=paragraphs;
    attachCitationHandlers();
  }else{
    section.hidden=true;
    body.innerHTML="";
  }
}

const LoadingOverlay = (()=>{
  const overlay = q("loading-overlay");
  const statusEl = q("loading-status");
  const fillEl = q("loading-progress-fill");
  const percentEl = q("loading-progress-label");
  const barEl = overlay?.querySelector?.(".loading-progress") || null;
  let current = 0;

  function clamp(value){
    if(Number.isNaN(value)) return 0;
    return Math.max(0, Math.min(100, Math.round(value)));
  }

  function renderProgress(){
    if(!fillEl) return;
    const ratio = current / 100;
    fillEl.style.transform = `scaleX(${ratio})`;
    if(percentEl) percentEl.textContent = `${current}%`;
    if(barEl) barEl.setAttribute("aria-valuenow", String(current));
  }

  function setProgress(value){
    const next = clamp(value);
    if(next <= current) return;
    current = next;
    renderProgress();
  }

  function reset(){
    current = 0;
    if(fillEl){
      fillEl.style.transform = "scaleX(0)";
    }
    if(percentEl){
      percentEl.textContent = "0%";
    }
    if(barEl){
      barEl.setAttribute("aria-valuenow", "0");
    }
  }

  function show(message){
    if(!overlay) return;
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    overlay.setAttribute("aria-busy", "true");
    reset();
    if(statusEl) statusEl.textContent = message || "Preparing your action plan…";
    setProgress(5);
  }

  function update(value, message){
    if(!overlay) return;
    if(message && statusEl) statusEl.textContent = message;
    setProgress(value);
  }

  function hide(message){
    if(!overlay) return;
    if(message && statusEl) statusEl.textContent = message;
    setProgress(100);
    overlay.setAttribute("aria-busy", "false");
    setTimeout(()=>{
      overlay.hidden = true;
      overlay.setAttribute("aria-hidden", "true");
      reset();
    }, 360);
  }

  return { show, update, hide };
})();


/* ==========================
   Rendering
   ========================== */
function renderSkeleton(n=3){
  renderActionPlan("");
  resetResourceIndex();
  setPromptOverlay(true);
  const emptyState = q("empty-state");
  if(emptyState) emptyState.hidden = true;
  const themesSummary = q("themes-summary");
  if(themesSummary) themesSummary.hidden = true;
  const themeList = q("themes-list");
  if(themeList) themeList.innerHTML = "";
  const track = q("carousel-track");
  if(track){
    track.innerHTML = Array.from({length:Math.max(1,n)}).map((_, idx)=>`
      <div class="carousel-slide skeleton-slide" data-slide-index="${idx}" aria-hidden="${idx===0?"false":"true"}">
        <div class="result-skeleton skeleton"></div>
      </div>
    `).join("");
    track.style.transform = "translateX(0%)";
  }
  const carousel = q("results-carousel");
  if(carousel) carousel.hidden = false;
  const meta = q("carousel-meta");
  if(meta){
    meta.hidden = false;
    meta.textContent = "Loading results…";
  }
  const prev = q("carousel-prev");
  const next = q("carousel-next");
  if(prev) prev.disabled = true;
  if(next) next.disabled = true;
  carouselState.slides = [];
  carouselState.themes = [];
  carouselState.currentSlide = 0;
  syncPromptSpacer();
}
function renderEmpty(){
  clearCarousel();
  const emptyState = q("empty-state");
  if(emptyState) emptyState.hidden = false;
  q("results-count").textContent="";
  renderActionPlan("");
  resetResourceIndex();
  setPromptOverlay(true);
}

function renderResourceCard(h){
  const md=h.metadata||{};
  const name=val(md.resource_name);
  const org=val(md.organization_name,"—");
  const cats=Array.isArray(md.categories)?md.categories:[];
  const langs=Array.isArray(md.languages)?md.languages:[];
  const fees=val(md.fees,"—");
  const hours=val(md.hours_notes||(md.hours&&md.hours.notes),"—");
  const addr=addressFrom(md);
  const phone=val(md.phone,"");
  const website=val(md.website,"");
  const email=val(md.email,"");
  const lastUpdated=val(md.last_updated,"—");
  const county=val(md.county,"—");
  const city=val(md.city,"—");
  const zip=val(md.zip_code,"—");
  const score=h.score?.toFixed?.(3)??"—";
  const phoneHref=telHref(phone);
  const mapHref=mapsHref(addr);
  const webHref=website&&website!=="Not provided"?website:null;
  const detailText=val(md.text,"—");
  const summary = val(h.model_summary, "—");
  const rid = resourceId(h);

  return `
    <article class="result-card" data-id="${escapeHTML(rid)}">
      <div class="card-inner">
        <div class="card-head">
          <div>
            <h3 class="card-title">${name}</h3>
            <p class="card-sub">${org}</p>
          </div>
          <div class="small">score ${score}</div>
        </div>

        <p class="card-summary">${summary}</p>

        <div class="badges">
          ${cats.map(c=>`<span class="badge">${c}</span>`).join("")}
          ${langs.map(l=>`<span class="badge lang">${l}</span>`).join("")}
        </div>

        <div class="meta-grid">
          <div class="meta"><label>Address</label><div>${addr}</div></div>
          <div class="meta"><label>Hours</label><div>${hours}</div></div>
          <div class="meta"><label>Cost / Fees</label><div>${fees}</div></div>
        </div>

        <div class="actions-row">
          ${phoneHref?`<a class="action" href="${phoneHref}">${icon('phone')}Call</a>`:""}
          ${webHref?`<a class="action" href="${webHref}" target="_blank" rel="noopener">${icon('globe')}Website</a>`:""}
          ${mapHref?`<a class="action" href="${mapHref}" target="_blank" rel="noopener">${icon('map')}Map</a>`:""}
          ${email&&email!=="Not provided"?`<a class="action" href="mailto:${email}">${icon('mail')}Email</a>`:""}
          <button class="action copy" data-copy="${addr}">${icon('copy')}Copy address</button>
          ${phone&&phone!=="Not provided"?`<button class="action copy" data-copy="${phone}">${icon('copy')}Copy phone</button>`:""}
        </div>

        <div class="split" style="margin-top:10px;">
          <div class="small">City ${city} • County ${county} • ZIP ${zip}</div>
          <div class="small">Last updated ${lastUpdated}</div>
        </div>

        <details style="margin-top:10px;">
          <summary style="cursor:pointer">More details (embedded text)</summary>
          <div class="meta" style="margin-top:8px;">
            <label>Text used for embedding</label>
            <div style="white-space:pre-wrap">${detailText}</div>
          </div>
        </details>
      </div>
    </article>
  `;
}

function attachCopyHandlers(){
  document.querySelectorAll(".action.copy").forEach(btn=>{
    btn.addEventListener("click", ()=>{
      const text = btn.getAttribute("data-copy") || "";
      if(!text || text==="Not provided") return;
      navigator.clipboard.writeText(text).then(()=> showToast("Copied to clipboard"));
    });
  });
}

function renderGroupedResults(grouped){
  const emptyState = q("empty-state");
  if(emptyState) emptyState.hidden = true;
  setPromptOverlay(true);
  ensureCarouselControls();

  const entries = Object.entries(grouped || {});
  const track = q("carousel-track");
  const carousel = q("results-carousel");
  const themesSummary = q("themes-summary");
  const themeList = q("themes-list");
  const meta = q("carousel-meta");

  let slideOffset = 0;
  const themes = [];
  const slides = [];

  entries.forEach(([slug, hits])=>{
    const validHits = Array.isArray(hits) ? hits : [];
    if(!validHits.length) return;
    const label = slug === "general" ? "Recommended Resources" : slugToTitle(slug);
    const themeIndex = themes.length;
    themes.push({ slug, label, count: validHits.length, start: slideOffset });
    validHits.forEach(hit=>{
      slides.push({ html: renderResourceCard(hit), themeIndex });
    });
    slideOffset += validHits.length;
  });

  if(!slides.length){
    renderEmpty();
    return;
  }

  carouselState.themes = themes.map((theme, idx)=>({ ...theme, index: idx }));
  carouselState.slides = slides.map((slide, idx)=>({ ...slide, slideIndex: idx }));
  carouselState.currentSlide = 0;

  if(themeList){
    themeList.innerHTML = carouselState.themes.map(theme=>`
      <button type="button" class="theme-chip" role="listitem" data-theme-index="${theme.index}" aria-pressed="${theme.index===0?"true":"false"}">
        ${escapeHTML(theme.label)}<span class="count">${theme.count}</span>
      </button>
    `).join("");
  }

  if(themesSummary) themesSummary.hidden = false;

  if(track){
    track.innerHTML = carouselState.slides.map(slide=>`
      <div class="carousel-slide" data-slide-index="${slide.slideIndex}" data-theme-index="${slide.themeIndex}" aria-hidden="true">
        ${slide.html}
      </div>
    `).join("");
    track.style.transform = "translateX(0%)";
  }

  if(carousel) carousel.hidden = false;
  if(meta){
    meta.hidden = false;
    meta.textContent = "";
  }

  attachCopyHandlers();
  updateResourceIndex();
  setActiveSlide(0, { scroll: false });
  syncPromptSpacer();
}

/* ==========================
   App logic
   ========================== */
async function onSubmit(e){
  e.preventDefault();
  const status=q("status"), btn=q("submit-btn");
  const payload={
    query:q("query").value||"",
    city:q("city").value||null,
    county:q("county").value||null,
    zip_code:q("zip_code").value||null,
    language:q("language").value||null,
    free_only:q("free_only").checked||null,
    top_k:Number(q("top_k").value||8),
    top_results:Number(q("top_results").value||5)
  };

  status.textContent="Searching…";
  btn.disabled=true; q("mini-indicator").hidden=false;
  LoadingOverlay.show("Analyzing your request…");
  LoadingOverlay.update(20, "Analyzing needs and filters…");
  renderSkeleton(3);

  let hadError=false;
  try{
    const fetchPromise = fetch("/ask",{
      method:"POST",
      headers:{"content-type":"application/json"},
      body:JSON.stringify(payload)
    });
    LoadingOverlay.update(45, "Retrieving matching resources…");
    const res=await fetchPromise;
    if(!res.ok){ status.textContent=`Error ${res.status}`; renderEmpty(); showToast("Request failed."); hadError=true; return; }
    LoadingOverlay.update(60, "Processing resource details…");
    const data=await res.json();
    const grouped=data.grouped_results||{};
    const entries=Object.entries(grouped).filter(([, arr])=>Array.isArray(arr)&&arr.length);
    const filteredGrouped=Object.fromEntries(entries);
    const total=entries.reduce((acc,[,arr])=>acc+arr.length,0);
    if(!total){
      renderEmpty();
    }else{
      renderGroupedResults(filteredGrouped);
      const needCount = entries.length;
      q("results-count").textContent = `${total} resources across ${needCount} theme${needCount===1?"":"s"}`;
      q("empty-state").hidden=true;
    }
    LoadingOverlay.update(82, "Summarizing resources…");
    renderActionPlan(data.action_plan||"");
    LoadingOverlay.update(94, "Drafting action plan…");
    status.textContent=`Done. ${total} resource(s).`;
  }catch(err){
    console.error(err);
    status.textContent="Error";
    renderEmpty();
    hadError=true;
  }finally{
    q("mini-indicator").hidden=true;
    btn.disabled=false;
    LoadingOverlay.hide(hadError ? "Something went wrong" : "Action plan ready");
  }
}

function onReset(){
  q("ask-form").reset();
  q("query").value="";
  q("results-count").textContent="";
  q("status").textContent="Ready";
  clearCarousel();
  const emptyState = q("empty-state");
  if(emptyState) emptyState.hidden = true;
  renderActionPlan("");
  resetResourceIndex();
  setPromptOverlay(false);
  syncPromptSpacer();
}
function onExampleClick(e){ if(!e.target.classList.contains("ex")) return; q("query").value=e.target.textContent.trim(); q("query").focus(); }

document.getElementById("ask-form").addEventListener("submit", onSubmit);
document.getElementById("reset-btn").addEventListener("click", onReset);
document.querySelector(".chips").addEventListener("click", onExampleClick);
ensureCarouselControls();
window.addEventListener("resize", ()=> syncPromptSpacer());
syncPromptSpacer();
