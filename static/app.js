"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  options: { Store: [], Brand: [], Category: [], "Form Factor": [] },
  rows: [],
  sort: { key: "rank", dir: 1 },
};

// ---------------------------------------------------------------- helpers
async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
}
const num = (v) => (v === "" || v == null ? null : Number(String(v).replace(/[$,]/g, "")));
const money = (v) => (v == null || isNaN(v) ? "—" : "$" + Number(v).toFixed(2));

// ---------------------------------------------------------------- tabs
$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    $$(".screen").forEach((s) => s.classList.remove("active"));
    $("#screen-" + tab.dataset.screen).classList.add("active");
    if (tab.dataset.screen === "dashboard") loadDashboard();
  });
});

// ---------------------------------------------------------------- autocomplete combo boxes
function setupCombo(inputId) {
  const input = $("#" + inputId);
  const list = $(`.suggestions[data-for="${inputId}"]`);
  const field = input.dataset.field;

  function render(q) {
    const all = state.options[field] || [];
    const matches = q ? all.filter((o) => o.toLowerCase().includes(q.toLowerCase())) : all;
    list.innerHTML = "";
    const exact = all.some((o) => o.toLowerCase() === q.toLowerCase());
    matches.slice(0, 8).forEach((opt) => {
      const li = document.createElement("li");
      li.textContent = opt;
      li.addEventListener("mousedown", (e) => { e.preventDefault(); input.value = opt; hide(); });
      list.appendChild(li);
    });
    if (q && !exact) {
      const li = document.createElement("li");
      li.innerHTML = `${q}<span class="new-tag">+ NEW</span>`;
      li.addEventListener("mousedown", (e) => { e.preventDefault(); hide(); });
      list.appendChild(li);
    }
    list.classList.toggle("show", list.children.length > 0);
  }
  const hide = () => list.classList.remove("show");

  input.addEventListener("input", () => render(input.value.trim()));
  input.addEventListener("focus", () => render(input.value.trim()));
  input.addEventListener("blur", () => setTimeout(hide, 120));
}
["store", "brand", "category", "form_factor"].forEach(setupCombo);

// ---------------------------------------------------------------- date field
const today = new Date().toISOString().slice(0, 10);
$("#date").value = today;
$("#date_picker").value = today;
$("#date_picker").addEventListener("change", (e) => { if (e.target.value) $("#date").value = e.target.value; });

// ---------------------------------------------------------------- validation
function clearErrors() {
  $$(".error").forEach((e) => (e.textContent = ""));
  $$("input").forEach((i) => i.classList.remove("invalid"));
}
function setError(id, msg) {
  const err = $(`.error[data-for="${id}"]`);
  if (err) err.textContent = msg;
  $("#" + id)?.classList.add("invalid");
}
function gather() {
  return {
    food_item: $("#food_item").value.trim(),
    store: $("#store").value.trim(),
    brand: $("#brand").value.trim(),
    category: $("#category").value.trim(),
    form_factor: $("#form_factor").value.trim(),
    date: $("#date").value.trim(),
    price: num($("#price").value),
    size: num($("#size").value),
    serving_size: num($("#serving_size").value),
    protein: num($("#protein").value),
    calories: num($("#calories").value),
  };
}
// Fields required for each action. Quick Compare doesn't need the detail fields.
const COMPARE_REQ = { food_item: "Food item", price: "Price", size: "Size", serving_size: "Serving size", protein: "Protein", calories: "Calories" };
const ADD_REQ = { ...COMPARE_REQ, store: "Store", brand: "Brand", category: "Category", form_factor: "Form Factor", date: "Date" };

function validate(data, required) {
  clearErrors();
  let ok = true;
  for (const [key, label] of Object.entries(required)) {
    const v = data[key];
    if (v === null || v === "" || (typeof v === "number" && isNaN(v))) {
      setError(key, `${label} is required`); ok = false;
    }
  }
  for (const k of ["size", "serving_size", "protein"]) {
    if (data[k] != null && data[k] <= 0) { setError(k, "Must be > 0"); ok = false; }
  }
  return ok;
}

// ---------------------------------------------------------------- quick compare + add
function ordinal(n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
function renderCompare(c) {
  $("#compare-empty").classList.add("hidden");
  const body = $("#compare-body");
  body.classList.remove("hidden");
  const o = c.overall;
  const cat = c.category_rank;

  // Build the neighbour preview with the current entry slotted into its correct
  // position by $/30g (rather than always pinned to the bottom).
  const itemName = ($("#food_item").value || "").trim() || "Your item";
  const peekRows = [
    ...c.neighbors.map((nb) => ({
      label: `${nb.food_item} · ${nb.store || ""}`,
      dollars: nb.dollars_per_30g, you: false,
    })),
    { label: `${itemName} (current entry)`, dollars: c.stats.dollars_per_30g, you: true },
  ].sort((a, b) => a.dollars - b.dollars);

  const peek = peekRows.map((row) => `
    <div class="peek-item ${row.you ? "you" : ""}">
      <span class="nm">${row.label}</span>
      <span class="pr">${money(row.dollars)}</span>
    </div>`).join("");

  body.innerHTML = `
    <div class="headline">
      <div class="big">${money(c.stats.dollars_per_30g)}</div>
      <div class="sub">per 30g protein</div>
    </div>
    <div class="metric-row">
      <div class="metric"><div class="v">${c.stats.calories_per_30g}</div><div class="k">cal / 30g</div></div>
      <div class="metric"><div class="v">${c.stats.serving_size_per_30g}</div><div class="k">serving / 30g</div></div>
    </div>
    <div class="rank-line">Ranked <b>${ordinal(o.rank)}</b> of ${o.total} overall in $/30g</div>
    ${cat ? `<div class="rank-line">Ranked <b>${ordinal(cat.rank)}</b> of ${cat.total} among <b>${c.category}</b></div>` : ""}
    <div class="rank-line">Cheaper than <b>${o.beats}</b> logged items (${o.percentile}%)</div>
    <div class="peek">
      <h4>Where it would sit</h4>
      ${peek}
    </div>`;
}

$("#btn-compare").addEventListener("click", async () => {
  const data = gather();
  if (!validate(data, COMPARE_REQ)) return;
  const btn = $("#btn-compare");
  btn.disabled = true;
  try {
    const c = await api("/api/quick-compare", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    });
    renderCompare(c);
  } catch (e) {
    toast("entry-toast", "Compare failed: " + e.message, false);
  } finally { btn.disabled = false; }
});

$("#btn-add").addEventListener("click", async () => {
  const data = gather();
  if (!validate(data, ADD_REQ)) {
    $("#details-group").open = true; // reveal the section holding the missing fields
    return;
  }
  const btn = $("#btn-add");
  btn.disabled = true;
  try {
    const res = await api("/api/entries", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    });
    renderCompare(res.compare);
    toast("entry-toast", `Added “${data.food_item}” (row ${res.row}) ✓`, true);
    await loadOptions(); // pick up any new dropdown values
  } catch (e) {
    toast("entry-toast", "Add failed: " + e.message, false);
  } finally { btn.disabled = false; }
});

function toast(id, msg, ok) {
  const el = $("#" + id);
  el.textContent = msg;
  el.className = "toast " + (ok ? "ok" : "err");
}

// ---------------------------------------------------------------- dashboard
function fuzzyMatch(needle, hay) {
  if (!needle) return true;
  const n = needle.toLowerCase().split(/\s+/).filter(Boolean);
  const h = (hay || "").toLowerCase();
  return n.every((tok) => h.includes(tok)); // token-subset fuzzy match
}
function fillSelect(sel, values) {
  sel.innerHTML = `<option value="">All</option>` + values.map((v) => `<option>${v}</option>`).join("");
}
function dashRows() {
  const food = $("#f_food").value.trim();
  const store = $("#f_store").value, brand = $("#f_brand").value;
  const cat = $("#f_category").value, form = $("#f_form").value;
  return state.rows.filter((r) =>
    fuzzyMatch(food, r["Food Item"]) &&
    (!store || r["Store"] === store) &&
    (!brand || r["Brand"] === brand) &&
    (!cat || r["Category"] === cat) &&
    (!form || r["Form Factor"] === form)
  );
}
function updateSortIndicators() {
  $$("#data-table th[data-sort]").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    if (th.dataset.sort === state.sort.key) {
      th.classList.add(state.sort.dir === 1 ? "sorted-asc" : "sorted-desc");
    }
  });
}
function renderDashboard() {
  updateSortIndicators();
  const rows = dashRows();
  const dollars = (r) => num(r["$ / 30g protein"]);
  // Stat cards
  const valid = rows.filter((r) => dollars(r) != null);
  const best = valid.reduce((a, b) => (a == null || dollars(b) < dollars(a) ? b : a), null);
  const avg = valid.length ? valid.reduce((s, r) => s + dollars(r), 0) / valid.length : null;
  $("#stat-cards").innerHTML = `
    <div class="stat"><div class="k">Items shown</div><div class="v">${rows.length}</div></div>
    <div class="stat"><div class="k">Best value / 30g</div><div class="v">${best ? money(dollars(best)) : "—"}</div><div class="d">${best ? best["Food Item"] : ""}</div></div>
    <div class="stat"><div class="k">Average $ / 30g</div><div class="v">${avg ? money(avg) : "—"}</div></div>`;

  // Table sort
  const { key, dir } = state.sort;
  const getter = {
    rank: (r) => num(r["Rank"]) ?? 9e9,
    dollars: (r) => dollars(r) ?? 9e9,
    cals: (r) => num(r["Calories / 30g"]) ?? 9e9,
  }[key] || ((r) => (r[key] || "").toString().toLowerCase());
  rows.sort((a, b) => { const x = getter(a), y = getter(b); return x < y ? -dir : x > y ? dir : 0; });

  // Always highlight the lowest $/30g (best value) row, regardless of the sort.
  $("#data-table tbody").innerHTML = rows.map((r) => `
    <tr class="${r === best ? "row-extreme" : ""}">
      <td>${r["Rank"] || ""}</td>
      <td>${r["Food Item"] || ""}</td>
      <td>${r["Store"] || ""}</td>
      <td>${r["Brand"] || ""}</td>
      <td>${r["Category"] || ""}</td>
      <td class="ctr">${money(dollars(r))}</td>
      <td class="ctr">${r["Calories / 30g"] || ""}</td>
      <td>${r["Date"] || ""}</td>
    </tr>`).join("") || `<tr><td colspan="8" style="text-align:center;color:var(--muted)">No matches</td></tr>`;
}
$$("#data-table th").forEach((th) => th.addEventListener("click", () => {
  const key = th.dataset.sort;
  state.sort = { key, dir: state.sort.key === key ? -state.sort.dir : 1 };
  renderDashboard();
}));
["f_food", "f_store", "f_brand", "f_category", "f_form"].forEach((id) =>
  $("#" + id).addEventListener("input", renderDashboard));
$("#btn-reset-filters").addEventListener("click", () => {
  ["f_food", "f_store", "f_brand", "f_category", "f_form"].forEach((id) => ($("#" + id).value = ""));
  renderDashboard();
});

async function loadDashboard() {
  try {
    const { rows } = await api("/api/data");
    state.rows = rows;
    fillSelect($("#f_store"), uniq(rows, "Store"));
    fillSelect($("#f_brand"), uniq(rows, "Brand"));
    fillSelect($("#f_category"), uniq(rows, "Category"));
    fillSelect($("#f_form"), uniq(rows, "Form Factor"));
    renderDashboard();
  } catch (e) {
    $("#stat-cards").innerHTML = `<div class="stat"><div class="k">Error</div><div class="v">⚠</div><div class="d">${e.message}</div></div>`;
  }
}
const uniq = (rows, key) => [...new Set(rows.map((r) => (r[key] || "").toString().trim()).filter(Boolean))].sort();

// ---------------------------------------------------------------- bootstrap
async function loadOptions() {
  try { state.options = await api("/api/options"); } catch {}
}
async function loadVersion() {
  try { $("#version").textContent = (await api("/api/version")).version; } catch {}
}
loadOptions();
loadVersion();
