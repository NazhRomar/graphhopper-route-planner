/*
 * app.js  -  Route Planner web page
 *
 * Talks to our FastAPI backend (/api/route and /api/compare), which calls
 * GraphHopper. The user's GraphHopper key is kept in this browser's local
 * storage and sent in the X-GraphHopper-Key header.
 *
 * Results are also saved in local storage for 10 minutes, so repeating a
 * trip costs no GraphHopper requests (the free plan has a per-minute limit).
 */
const KEY_STORE = "graphhopper_key";
const CACHE_PREFIX = "trip:";
const CACHE_MS = 10 * 60 * 1000;

const $ = (id) => document.getElementById(id);

// Local storage can be blocked (private windows, strict settings), so never
// let a storage error break the page
function storage(action) {
  try {
    return action(window.localStorage);
  } catch {
    return null;
  }
}

// ------------------------------------------------------------------ toasts
function toast(message, kind = "info") {
  const box = document.createElement("div");
  box.className = `toast toast-${kind}`;
  box.setAttribute("role", kind === "error" ? "alert" : "status");
  box.textContent = message;
  $("toasts").append(box);
  setTimeout(() => box.classList.add("leaving"), 4500);
  setTimeout(() => box.remove(), 4900);
}

// Small helper to build elements without innerHTML (place names come from
// GraphHopper, so they are always inserted as text)
function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
}

// ----------------------------------------------------------------- API key
function currentKey() {
  return $("key").value.trim();
}

$("key").value = storage((s) => s.getItem(KEY_STORE)) || "";

$("save-key").addEventListener("click", () => {
  const key = currentKey();
  if (!key) {
    toast("Paste your GraphHopper key first.", "warn");
    return;
  }
  const saved = storage((s) => (s.setItem(KEY_STORE, key), true));
  toast(saved ? "Key saved in this browser only." : "This browser blocks local storage, so the key is kept only until you close the tab.",
        saved ? "success" : "warn");
});

$("clear-key").addEventListener("click", () => {
  storage((s) => s.removeItem(KEY_STORE));
  $("key").value = "";
  toast("Key removed from this browser.");
});

$("toggle-key").addEventListener("click", () => {
  const hidden = $("key").type === "password";
  $("key").type = hidden ? "text" : "password";
  $("toggle-key").textContent = hidden ? "Hide" : "Show";
  $("toggle-key").setAttribute("aria-label", hidden ? "Hide key" : "Show key");
});

$("carpool").addEventListener("change", () => {
  $("people-row").hidden = !$("carpool").checked;
});

// ------------------------------------------------------------ trip inputs
function unit() {
  return document.querySelector('input[name="unit"]:checked').value;
}

function tripParams(withMode) {
  const params = new URLSearchParams();
  $("stops").value.split("\n").map((s) => s.trim()).filter(Boolean)
    .forEach((stop) => params.append("stops", stop));
  if (withMode) params.set("mode", $("mode").value);
  params.set("unit", unit());
  params.set("price_per_liter", $("price").value || 0);
  params.set("km_per_liter", $("kmpl").value || 1);
  params.set("people", $("carpool").checked ? $("people").value || 2 : 1);
  params.set("weight_kg", $("weight").value || 65);
  return params;
}

// ------------------------------------------------------------- API calls
function pruneCache() {
  storage((s) => {
    for (let i = s.length - 1; i >= 0; i--) {
      const name = s.key(i);
      if (!name.startsWith(CACHE_PREFIX)) continue;
      const entry = JSON.parse(s.getItem(name) || "{}");
      if (!entry.at || Date.now() - entry.at > CACHE_MS) s.removeItem(name);
    }
  });
}

async function callApi(path, params) {
  const key = currentKey();
  if (!key) {
    toast("Add your GraphHopper API key in the settings first.", "error");
    $("key").focus();
    return null;
  }

  const cacheId = `${CACHE_PREFIX}${path}?${params}`;
  const saved = storage((s) => JSON.parse(s.getItem(cacheId)));
  if (saved && Date.now() - saved.at < CACHE_MS) {
    toast("Same trip as before: showing the saved result, no GraphHopper requests used.");
    return saved.data;
  }

  let response;
  try {
    response = await fetch(`/api/${path}?${params}`, {
      headers: { "X-GraphHopper-Key": key },
    });
  } catch {
    toast("Could not reach the server. Check your connection.", "error");
    return null;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // FastAPI sends a list for input validation errors, a string otherwise
    const message = typeof data.detail === "string" ? data.detail : "Check your inputs and try again.";
    toast(message, message.includes("limit") ? "warn" : "error");
    return null;
  }

  pruneCache();
  storage((s) => s.setItem(cacheId, JSON.stringify({ at: Date.now(), data })));
  return data;
}

async function busy(button, task) {
  const buttons = [$("get-route"), $("compare")];
  const label = button.textContent;
  buttons.forEach((b) => (b.disabled = true));
  button.textContent = "Working...";
  try {
    await task();
  } finally {
    buttons.forEach((b) => (b.disabled = false));
    button.textContent = label;
  }
}

// ------------------------------------------------------------- rendering
const fmt = (n, digits = 1) =>
  Number(n).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });

function metric(label, value) {
  return el("div", { className: "metric" }, el("span", { textContent: label }), el("strong", { textContent: value }));
}

function table(target, headers, rows, numeric = []) {
  const head = el("tr", {}, ...headers.map((h) => el("th", { textContent: h })));
  const body = rows.map((row) =>
    el("tr", { className: row._failed ? "failed" : "" },
      ...headers.map((h) => el("td", {
        className: numeric.includes(h) ? "num" : "",
        textContent: row[h] ?? "",
      }))));
  target.replaceChildren(el("thead", {}, head), el("tbody", {}, ...body));
}

function bars(target, items) {
  const max = Math.max(...items.map((i) => i.value), 1);
  target.replaceChildren(...items.map((i) =>
    el("div", { className: "bar" },
      el("span", { className: "bar-label", textContent: i.label, title: i.label }),
      el("div", { className: "bar-track" },
        el("div", { className: "bar-fill", style: `width:${(i.value / max) * 100}%` })),
      el("span", { className: "bar-value", textContent: i.text }))));
}

let map;
let mapLayers;

function drawMap(route) {
  if (!map) {
    map = L.map("map");
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    mapLayers = L.layerGroup().addTo(map);
  }
  mapLayers.clearLayers();
  const line = L.polyline(route.line, { color: "#2563eb", weight: 5 }).addTo(mapLayers);
  route.stops.forEach((stop, i) => {
    L.circleMarker([stop.lat, stop.lng], { radius: 8, color: "#ffffff", weight: 2, fillColor: "#dc2626", fillOpacity: 1 })
      .bindTooltip(`${i + 1}. ${stop.name}`)
      .addTo(mapLayers);
  });
  map.invalidateSize();
  map.fitBounds(line.getBounds(), { padding: [24, 24] });
}

let lastSteps = [];

function renderRoute(r) {
  const currency = $("currency").value.trim() || "PHP";
  const cards = [metric("Total distance", `${fmt(r.distance)} ${r.unit}`), metric("Trip time", r.time_text)];
  let note;
  if (r.fuel_cost !== undefined) {
    cards.push(metric("Gas cost (total)", `${currency} ${fmt(r.fuel_cost, 2)}`));
    if (r.people > 1) cards.push(metric(`Per person (${r.people} people)`, `${currency} ${fmt(r.cost_per_person, 2)}`));
    note = `About ${fmt(r.liters)} liters of gas.`;
  } else {
    cards.push(metric("Calories burned", `${fmt(r.calories_kcal, 0)} kcal`));
    note = "Estimate based on your weight and average speed. Real burn varies with fitness, hills and wind.";
  }
  $("metrics").replaceChildren(...cards);
  $("metric-note").textContent = note;

  $("route-result").hidden = false;
  drawMap(r);

  table($("places"), ["Stop", "You typed", "Found", "Type"],
    r.stops.map((s, i) => ({ Stop: i + 1, "You typed": s.query, Found: s.name, Type: s.type })));

  $("legs-block").hidden = r.legs.length < 2;
  bars($("legs"), r.legs.map((leg) => ({ label: leg.Leg, value: leg.Distance, text: `${fmt(leg.Distance)} ${r.unit} · ${leg.Time}` })));

  lastSteps = r.steps;
  table($("steps"), ["Step", "Direction", `Distance (${r.unit})`, "Time"],
    r.steps.map((s) => ({ Step: s.Step, Direction: s.Direction, [`Distance (${r.unit})`]: fmt(s.Distance, 2), Time: s.Time })),
    ["Step", `Distance (${r.unit})`, "Time"]);
}

function renderCompare(c) {
  const currency = $("currency").value.trim() || "PHP";
  $("compare-result").hidden = false;
  table($("compare-table"), ["Mode", `Distance (${c.unit})`, "Time", "Gas cost", "Cost per person", "Calories (kcal)"],
    c.modes.map((m) => ({
      _failed: m.Minutes === null,
      Mode: m.Mode,
      [`Distance (${c.unit})`]: m.Distance === null ? "" : fmt(m.Distance),
      Time: m.Time,
      "Gas cost": m["Fuel cost"] ? `${currency} ${fmt(m["Fuel cost"], 2)}` : "",
      "Cost per person": m["Cost per person"] ? `${currency} ${fmt(m["Cost per person"], 2)}` : "",
      "Calories (kcal)": m["Calories (kcal)"] ? fmt(m["Calories (kcal)"], 0) : "",
    })),
    [`Distance (${c.unit})`, "Gas cost", "Cost per person", "Calories (kcal)"]);

  const ok = c.modes.filter((m) => m.Minutes !== null);
  bars($("compare-bars"), ok.map((m) => ({ label: m.Mode, value: m.Minutes, text: m.Time })));

  const fastest = c.modes.find((m) => m.Mode === c.fastest);
  const summary = fastest ? `Fastest option: ${fastest.Mode} (${fastest.Time})` : "No mode returned a route for these stops.";
  $("fastest").replaceChildren(summary,
    ...Object.entries(c.errors).map(([mode, reason]) => el("p", { className: "warning", textContent: `${mode}: ${reason}` })));
  if (Object.keys(c.errors).length) toast(`Some modes have no route: ${Object.keys(c.errors).join(", ")}.`, "warn");
}

// -------------------------------------------------------------- buttons
$("get-route").addEventListener("click", (e) =>
  busy(e.currentTarget, async () => {
    const data = await callApi("route", tripParams(true));
    if (data) renderRoute(data);
  }));

$("compare").addEventListener("click", (e) =>
  busy(e.currentTarget, async () => {
    const data = await callApi("compare", tripParams(false));
    if (data) renderCompare(data);
  }));

$("download").addEventListener("click", () => {
  const quote = (v) => `"${String(v).replaceAll('"', '""')}"`;
  const rows = [["Step", "Direction", "Distance", "Time"], ...lastSteps.map((s) => [s.Step, s.Direction, s.Distance, s.Time])];
  const blob = new Blob([rows.map((r) => r.map(quote).join(",")).join("\n")], { type: "text/csv" });
  const link = el("a", { href: URL.createObjectURL(blob), download: "directions.csv" });
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  toast("Saved directions.csv", "success");
});

if (!currentKey()) toast("Add your GraphHopper API key in the settings to start.");
