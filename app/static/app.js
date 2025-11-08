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

function resetResourceIndex(){
  Object.keys(resourceIndex).forEach(key=>{ delete resourceIndex[key]; });
}

function updateResourceIndex(){
  resetResourceIndex();
  document.querySelectorAll(".result-card[data-id]").forEach(card=>{
    const id = card.getAttribute("data-id");
    if(!id) return;
    const title = card.querySelector(".card-title");
    resourceIndex[id] = {
      name: (title?.textContent || `Resource ${id}`).trim(),
      element: card
    };
  });
}

function escapeHTML(str=""){
  return String(str).replace(/[&<>"']/g, ch=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[ch]);
}

function attachCitationHandlers(){
  document.querySelectorAll(".cite-link").forEach(btn=>{
    btn.addEventListener("click", ()=>{
      const id = btn.getAttribute("data-id");
      if(!id) return;
      const info = resourceIndex[id];
      if(!info || !info.element) return;
      info.element.scrollIntoView({behavior:"smooth", block:"center"});
      info.element.classList.add("highlighted");
      setTimeout(()=>info.element.classList.remove("highlighted"), 1600);
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
  q("results").innerHTML = Array.from({length:n}).map(()=>`<div class="result-skeleton skeleton"></div>`).join("");
}
function renderEmpty(){
  q("results").innerHTML="";
  q("empty-state").hidden=false;
  q("results-count").textContent="";
  renderActionPlan("");
  resetResourceIndex();
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
  const rid = (h.id ?? h.service_id ?? md.resource_id ?? md.id ?? "").toString();

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
  const results=q("results");
  q("empty-state").hidden=true;

  const sections = Object.entries(grouped||{}).map(([slug, hits])=>{
    const cards = Array.isArray(hits) && hits.length
      ? hits.map(renderResourceCard).join("")
      : `<p class="muted no-results-msg">No resources matched yet.</p>`;
    const heading = slug==="general" ? "Recommended Resources" : slugToTitle(slug);
    return `
      <section class="need-section">
        <h3 class="need-heading">${heading}</h3>
        <div class="need-results">${cards}</div>
      </section>
    `;
  });

  results.innerHTML = sections.join("");
  attachCopyHandlers();
  updateResourceIndex();
}

/* ==========================
   App logic
   ========================== */
async function onSubmit(e){
  e.preventDefault();
  const status=q("status"), btn=q("submit-btn"), resultsPanel = q("results-panel");
  const payload={
    query:q("query").value||"",
    city: q("city") ? q("city").value : null,
    county: q("county") ? q("county").value : null,
    zip_code: q("zip_code") ? q("zip_code").value : null,
    language: q("language") ? q("language").value : null,
    free_only: q("free_only") ? q("free_only").checked : null,
    top_k: q("top_k") ? Number(q("top_k").value) : 8,
    top_results: q("top_results") ? Number(q("top_results").value) : 5
  };

  status.textContent="Searching…";
  btn.disabled=true; q("mini-indicator").hidden=false;
  LoadingOverlay.show("Analyzing your request…");
  LoadingOverlay.update(20, "Analyzing needs and filters…");
  resultsPanel.hidden = false;
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
  q("query").value=""; q("results").innerHTML=""; q("results-count").textContent="";
  q("empty-state").hidden=true; q("status").textContent="Ready";
  q("results-panel").hidden = true;
  renderActionPlan("");
}
function onExampleClick(e){ if(!e.target.classList.contains("ex")) return; q("query").value=e.target.textContent.trim(); q("query").focus(); }

document.getElementById("ask-form").addEventListener("submit", onSubmit);
document.getElementById("reset-btn").addEventListener("click", onReset);
document.querySelector(".chips").addEventListener("click", onExampleClick);
