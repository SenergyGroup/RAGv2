let ADMIN_TOKEN = sessionStorage.getItem("ADMIN_TOKEN") || "";

function ensureToken(){
  if(ADMIN_TOKEN) return ADMIN_TOKEN;
  ADMIN_TOKEN = prompt("Enter ADMIN_TOKEN:");
  if(!ADMIN_TOKEN) alert("Admin token required.");
  sessionStorage.setItem("ADMIN_TOKEN", ADMIN_TOKEN);
  return ADMIN_TOKEN;
}

function q(id){ return document.getElementById(id); }
function arr(s){ return s && s !== "Unknown" ? s.split(",").map(x=>x.trim()).filter(Boolean) : []; }
function norm(s){ // "Unknown" -> ""
  if (s === "Unknown" || s === null || s === undefined) return "";
  return String(s).trim();
}

let CUR_INDEX = 0, TOTAL = 0;

async function loadSummary(){
  const r = await fetch("/api/admin/summary"); const d = await r.json();
  q("rec-total").textContent = d.total; q("reviewed-count").textContent = d.reviewed_count; q("dirty-count").textContent = d.dirty_count;
  TOTAL = d.total;
}

function F(x){ // force a visible value in the textbox
  if (Array.isArray(x)) return x.length ? x.join(", ") : "Unknown";
  const s = (x ?? "").toString().trim();
  return s ? s : "Unknown";
}

async function loadRecord(index){
  const r = await fetch(`/api/admin/record?index=${index}`);
  const d = await r.json();

  CUR_INDEX = d.index; TOTAL = d.total;
  q("rec-idx").textContent = CUR_INDEX + 1;
  q("rec-total").textContent = TOTAL;
  q("reviewed").checked = !!d.reviewed;

  const md = d.metadata || {};

  q("rid").value              = F(d.id || md.id);
  q("resource_name").value    = F(md.resource_name);
  q("organization_name").value= F(md.organization_name);
  q("categories").value       = F(md.categories);
  q("fees").value             = F(md.fees);
  q("languages").value        = F(md.languages);
  q("hours_notes").value      = F(md.hours_notes);
  q("street").value           = F(md.street);
  q("city").value             = F(md.city);
  q("state").value            = F(md.state);
  q("zip_code").value         = F(md.zip_code);
  q("county").value           = F(md.county);
  q("phone").value            = F(md.phone);
  q("website").value          = F(md.website);
  q("email").value            = F(md.email);
  q("last_updated").value     = F(md.last_updated);
  q("source_file").value      = F(md.source_file);

  // Embedded text
  q("text").value = (d.document && d.document.text) ? d.document.text : "Unknown";
}

function buildTextFromFields(){
  const name=q("resource_name").value, org=q("organization_name").value;
  const services = arr(q("categories").value);
  const fees = q("fees").value, langs = arr(q("languages").value);
  const hours = q("hours_notes").value;
  const city=q("city").value, county=q("county").value;
  return [
    `Resource: ${name} — ${org}`,
    `What it is: Description not provided.`, // You can extend: include a description field on Admin if you want
    services.length? `Services: ${services.join(", ")}` : "",
    fees? `Cost: ${fees}`:"",
    hours? `When: ${hours}`:"",
    (city||county)? `Where it operates: ${[city, county].filter(Boolean).join(", ")}`:"",
    langs.length? `Languages: ${langs.join(", ")}`:"",
    `Last updated: ${q("last_updated").value || "unknown"}`,
    `Source: ${q("source_file").value || "unknown"}`,
    `ID: ${q("rid").value}`
  ].filter(Boolean).join("\n");
}

async function saveCurrent(){
  ensureToken();
  const payload={
    id: q("rid").value,
    reviewed: q("reviewed").checked,
    text: q("text").value === "Unknown" ? "" : q("text").value,
    metadata: {
      resource_name:      norm(q("resource_name").value),
      organization_name:  norm(q("organization_name").value),
      categories:         arr(q("categories").value),
      fees:               norm(q("fees").value),
      languages:          arr(q("languages").value),
      hours_notes:        norm(q("hours_notes").value),
      street:             norm(q("street").value),
      city:               norm(q("city").value),
      state:              norm(q("state").value),
      zip_code:           norm(q("zip_code").value),
      county:             norm(q("county").value),
      phone:              norm(q("phone").value),
      website:            norm(q("website").value),
      email:              norm(q("email").value),
      last_updated:       norm(q("last_updated").value),
      source_file:        norm(q("source_file").value)
    }
  };
  const r = await fetch("/api/admin/update", {
    method:"POST",
    headers:{"content-type":"application/json","X-Admin-Token":ADMIN_TOKEN},
    body:JSON.stringify(payload)
  });
  const d = await r.json();
  q("reviewed-count").textContent = d.reviewed_count;
  q("dirty-count").textContent = d.dirty_count;
  q("admin-status").textContent = "Saved.";
}

async function saveAll(){
  ensureToken();
  q("admin-status").textContent = "Saving files…";
  const r = await fetch("/api/admin/save", {method:"POST", headers:{"X-Admin-Token":ADMIN_TOKEN}});
  await r.json();
  q("admin-status").textContent = "All saved to JSONL.";
}

async function upsert(only_dirty){
  ensureToken();
  q("admin-status").textContent = `Upserting (${only_dirty?"dirty":"all"})… this may take a while.`;
  const r = await fetch(`/api/admin/upsert?only_dirty=${only_dirty?"true":"false"}`, {method:"POST", headers:{"X-Admin-Token":ADMIN_TOKEN}});
  const d = await r.json();
  q("admin-status").textContent = `Upserted ${d.upserted} (errors ${d.errors}).`;
  await loadSummary();
}

document.getElementById("prev-btn").addEventListener("click", ()=> loadRecord(Math.max(0, CUR_INDEX-1)));
document.getElementById("next-btn").addEventListener("click", ()=> loadRecord(Math.min(TOTAL-1, CUR_INDEX+1)));
document.getElementById("jump-btn").addEventListener("click", ()=> loadRecord(Math.max(0, Math.min(TOTAL-1, Number(q("jump").value||0)-1))));
document.getElementById("gen-text").addEventListener("click", ()=> { q("text").value = buildTextFromFields(); });
document.getElementById("save").addEventListener("click", saveCurrent);
document.getElementById("save-all").addEventListener("click", saveAll);
document.getElementById("upsert-dirty").addEventListener("click", ()=> upsert(true));
document.getElementById("upsert-all").addEventListener("click", ()=> upsert(false));

(async function init(){
  await loadSummary();
  await loadRecord(0);
})();
