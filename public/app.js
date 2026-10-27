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
const CREDITS_STORE = "graphhopper_credits";
const FORM_STORE = "trip_form";
const CACHE_PREFIX = "trip:";
const CACHE_MS = 10 * 60 * 1000;
// Bump when the API's results change shape, so results saved by an older
// version of the page are fetched again instead of reused
const CACHE_VERSION = 2;
const MAX_STOPS = 10;
const DEFAULT_STOPS = ["Manila, Philippines", "Tagaytay, Philippines", "Batangas City, Philippines"];
const MODE_KEYS = { Driving: "car", Walking: "foot", Cycling: "bike" };
const MODE_ICONS = { car: "car", foot: "walk", bike: "bike" };
// Line colors in Compare (CSS variables, so dark mode can adjust them)
const MODE_COLORS = { Driving: "--mode-car", Walking: "--mode-walk", Cycling: "--mode-bike" };

const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------------ icons
// Inner SVG markup for every icon on the page (24x24, drawn with strokes)
const ICONS = {
  logo: '<circle cx="6" cy="19" r="2.5"/><circle cx="18" cy="5" r="2.5"/><path d="M8.5 19H16a3.5 3.5 0 0 0 0-7H8a3.5 3.5 0 0 1 0-7h7.5"/>',
  car: '<path d="M3 13l2-5a2 2 0 0 1 2-1h10a2 2 0 0 1 2 1l2 5v4a1 1 0 0 1-1 1h-1M3 13v4a1 1 0 0 0 1 1h1M3 13h18M9 18h6"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
  walk: '<circle cx="13" cy="4" r="2"/><path d="M10 21l2-6 3 3v3M7 12l3-4 4 1 2 3 3 1M12 15l-1.5-6"/>',
  bike: '<circle cx="6" cy="16" r="3.5"/><circle cx="18" cy="16" r="3.5"/><path d="M6 16l4-7h5l3 7M10 9l2.5 7H6M13 6h3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  swap: '<path d="M7 4v16M3 8l4-4 4 4M17 20V4M21 16l-4 4-4-4"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  "chevron-left": '<path d="M15 6l-6 6 6 6"/>',
  "chevron-right": '<path d="M9 6l6 6-6 6"/>',
  route: '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h8a3.5 3.5 0 0 0 0-7H8a3.5 3.5 0 0 1 0-7h8"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  fuel: '<path d="M4 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16M3 21h12M14 9h2a2 2 0 0 1 2 2v5a1.5 1.5 0 0 0 3 0V8l-3-3M7 7h4"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M3 20a6 6 0 0 1 12 0M16 4.5a3.5 3.5 0 0 1 0 7M21 20a6 6 0 0 0-4-5.6"/>',
  flame: '<path d="M12 3c1 3 5 5.5 5 10a5 5 0 0 1-10 0c0-2.4 1.3-4 2.5-5 .2 1.8 1 3 2 3 0-3-.5-5.5.5-8z"/>',
  left: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 6 6v5"/>',
  right: '<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 0 0-6 6v5"/>',
  straight: '<path d="M12 20V4M6 10l6-6 6 6"/>',
  uturn: '<path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
  roundabout: '<circle cx="12" cy="10" r="4"/><path d="M12 14v7M8.5 7.5L5 4"/>',
  flag: '<path d="M5 21V4h11l-2 4 2 4H5"/>',
  pin: '<path d="M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  success: '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
  warn: '<path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17h.01"/>',
  error: '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
};

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = ICONS[name]; // fixed markup from the list above, never user data
  return svg;
}

document.querySelectorAll("[data-icon]").forEach((n) => n.replaceWith(icon(n.dataset.icon)));

// Small helper to build elements without innerHTML (place names come from
// GraphHopper, so they are always inserted as text)
function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children.filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

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
  const box = el("div", { className: `toast toast-${kind}`, role: kind === "error" ? "alert" : "status" },
    icon(kind), el("span", { textContent: message }));
  $("toasts").append(box);
  setTimeout(() => box.classList.add("leaving"), 4500);
  setTimeout(() => box.remove(), 4900);
}

// ----------------------------------------------------------------- API key
const keyDialog = $("key-dialog");

function currentKey() {
  return $("key").value.trim();
}

// Today's GraphHopper credits for the saved key. The API passes them on with
// every result (from GraphHopper's rate-limit headers); the last numbers are
// kept in this browser until the daily reset.
let credits = null;

function untilReset(resetsAt) {
  const seconds = Math.max(0, resetsAt - Date.now() / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

// One badge for both: no key, key without numbers yet, or "used / limit"
function showKeyState() {
  const button = $("key-button");
  const saved = Boolean(currentKey());
  const low = credits && credits.remaining <= credits.limit * 0.1;
  button.dataset.state = !saved ? "missing" : credits && credits.remaining <= 0 ? "out" : low ? "low" : "saved";
  $("key-status").textContent = !saved ? "Add API key"
    : credits ? `${credits.used.toLocaleString()} / ${credits.limit.toLocaleString()}` : "API key";
  button.title = !saved ? "Add your GraphHopper API key"
    : credits ? `GraphHopper credits used today: ${credits.remaining.toLocaleString()} left, resets in ${untilReset(credits.resets_at)}. Click to change the key.`
    : "Click to change your GraphHopper API key";
}

function updateCredits(u) {
  if (!u || !u.limit) return;
  const low = u.limit * 0.1;
  const wasLow = credits && credits.remaining <= low;
  credits = u;
  storage((s) => s.setItem(CREDITS_STORE, JSON.stringify(u)));
  showKeyState();
  if (u.remaining <= low && !wasLow) toast(`Only ${u.remaining} GraphHopper credits left today.`, "warn");
}

function forgetCredits() {
  credits = null;
  storage((s) => s.removeItem(CREDITS_STORE));
}

$("key").value = storage((s) => s.getItem(KEY_STORE)) || "";
const savedCredits = storage((s) => JSON.parse(s.getItem(CREDITS_STORE)));
if (currentKey() && savedCredits && savedCredits.resets_at > Date.now() / 1000) credits = savedCredits;
showKeyState();

$("key-button").addEventListener("click", () => keyDialog.showModal());
keyDialog.addEventListener("click", (e) => {
  if (e.target === keyDialog) keyDialog.close(); // click on the backdrop
});

$("save-key").addEventListener("click", () => {
  const key = currentKey();
  if (!key) {
    toast("Paste your GraphHopper key first.", "warn");
    $("key").focus();
    return;
  }
  const changed = key !== storage((s) => s.getItem(KEY_STORE));
  const saved = storage((s) => (s.setItem(KEY_STORE, key), true));
  if (changed) forgetCredits(); // a different key has its own credits
  showKeyState();
  keyDialog.close();
  toast(saved ? "Key saved in this browser only." : "This browser blocks local storage, so the key is kept only until you close the tab.",
        saved ? "success" : "warn");
});

$("clear-key").addEventListener("click", () => {
  storage((s) => s.removeItem(KEY_STORE));
  $("key").value = "";
  forgetCredits();
  showKeyState();
  toast("Key removed from this browser.");
});

$("toggle-key").addEventListener("click", () => {
  const hidden = $("key").type === "password";
  $("key").type = hidden ? "text" : "password";
  $("toggle-key").textContent = hidden ? "Hide" : "Show";
});

// ------------------------------------------------------------------ stops
const letter = (i) => String.fromCharCode(65 + (i % 26));

function stopValues({ keepEmpty = false } = {}) {
  const values = [...document.querySelectorAll(".stop-input")].map((i) => i.value.trim());
  return keepEmpty ? values : values.filter(Boolean);
}

function renderStops(values) {
  const last = values.length - 1;
  $("stop-list").replaceChildren(...values.map((value, i) => {
    const input = el("input", {
      className: "stop-input",
      value,
      placeholder: i === 0 ? "Start" : i === last ? "Destination" : "Stop along the way",
      autocomplete: "off",
    });
    input.setAttribute("aria-label", `Stop ${letter(i)}`);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") $("get-route").click(); });
    input.addEventListener("input", saveForm);

    const remove = el("button", { type: "button", className: "icon-btn", title: "Remove stop", disabled: values.length <= 2 }, icon("x"));
    remove.setAttribute("aria-label", `Remove stop ${letter(i)}`);
    remove.addEventListener("click", () => {
      const all = stopValues({ keepEmpty: true });
      all.splice(i, 1);
      renderStops(all);
      saveForm();
    });
    return el("li", { className: "stop" }, el("span", { className: "pin", textContent: letter(i) }), input, remove);
  }));
  $("add-stop").disabled = values.length >= MAX_STOPS;
}

$("add-stop").addEventListener("click", () => {
  const all = stopValues({ keepEmpty: true });
  all.push("");
  renderStops(all);
  [...document.querySelectorAll(".stop-input")].at(-1).focus();
});

$("reverse").addEventListener("click", () => {
  renderStops(stopValues({ keepEmpty: true }).reverse());
  saveForm();
});

// Remember the last trip in this browser, for convenience
function selectedMode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

function saveForm() {
  storage((s) => s.setItem(FORM_STORE, JSON.stringify({ stops: stopValues({ keepEmpty: true }), mode: selectedMode() })));
}

const savedForm = storage((s) => JSON.parse(s.getItem(FORM_STORE))) || {};
renderStops(savedForm.stops?.length >= 2 ? savedForm.stops : DEFAULT_STOPS);
const savedMode = document.querySelector(`input[name="mode"][value="${savedForm.mode}"]`);
if (savedMode) savedMode.checked = true;
document.querySelectorAll('input[name="mode"]').forEach((r) => r.addEventListener("change", saveForm));

$("carpool").addEventListener("change", () => {
  $("people-row").hidden = !$("carpool").checked;
});

// ------------------------------------------------------------ trip inputs
function unit() {
  return document.querySelector('input[name="unit"]:checked').value;
}

function tripParams(withMode) {
  const params = new URLSearchParams();
  stopValues().forEach((stop) => params.append("stops", stop));
  if (withMode) params.set("mode", selectedMode());
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
      if (entry.v !== CACHE_VERSION || !entry.at || Date.now() - entry.at > CACHE_MS) s.removeItem(name);
    }
  });
}

async function callApi(path, params) {
  if (!currentKey()) {
    toast("Add your GraphHopper API key first.", "error");
    keyDialog.showModal();
    return null;
  }
  if (params.getAll("stops").length < 2) {
    toast("Enter at least a start and a destination.", "warn");
    return null;
  }

  const cacheId = `${CACHE_PREFIX}${path}?${params}`;
  const saved = storage((s) => JSON.parse(s.getItem(cacheId)));
  if (saved && saved.v === CACHE_VERSION && Date.now() - saved.at < CACHE_MS) {
    toast("Same trip as before: showing the saved result, no GraphHopper requests used.");
    return saved.data;
  }

  let response;
  try {
    response = await fetch(`/api/${path}?${params}`, {
      headers: { "X-GraphHopper-Key": currentKey() },
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
  storage((s) => s.setItem(cacheId, JSON.stringify({ v: CACHE_VERSION, at: Date.now(), data })));
  updateCredits(data.usage);
  return data;
}

async function busy(button, task) {
  const buttons = [$("get-route"), $("compare")];
  const label = button.textContent;
  buttons.forEach((b) => (b.disabled = true));
  button.classList.add("is-loading");
  button.textContent = "Working";
  document.body.classList.add("loading");
  try {
    await task();
  } finally {
    buttons.forEach((b) => (b.disabled = false));
    button.classList.remove("is-loading");
    button.textContent = label;
    document.body.classList.remove("loading");
  }
}

// ------------------------------------------------- panel: tabs and layout
const panel = $("panel");
const isPhone = () => window.matchMedia("(max-width: 760px)").matches;

// The last results, so switching tabs can put the matching lines on the map
let lastRoute = null;
let lastCompare = null;
let comparePick = null; // the mode highlighted in Compare

function showTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.setAttribute("aria-selected", active);
    $(`tab-${tab.dataset.tab}`).hidden = !active;
  });
  document.querySelector(".panel-body").scrollTop = 0;

  // Route shows its one line; Compare shows every mode with one highlighted
  if (name === "route" && lastRoute) {
    drawRoute(lastRoute);
    showSummary(routeSummary(lastRoute));
  } else if (name === "compare" && lastCompare) {
    drawCompare(lastCompare);
    selectCompare(comparePick);
  }
}

function enableTab(name) {
  document.querySelector(`.tab[data-tab="${name}"]`).disabled = false;
}

document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => showTab(tab.dataset.tab)));

// Desktop: hide the panel to see the whole map
function setPanelHidden(hidden) {
  document.body.classList.toggle("panel-hidden", hidden);
  $("expand").hidden = !hidden;
  setTimeout(fitRoute, 280); // after the slide animation
}
$("collapse").addEventListener("click", () => setPanelHidden(true));
$("expand").addEventListener("click", () => setPanelHidden(false));

// Re-fit the route once the panel finishes sliding or resizing (the timers
// above are a fallback for browsers with animations turned off)
panel.addEventListener("transitionend", (e) => { if (e.target === panel) fitRoute(); });

// Phone: the panel is a bottom sheet with three heights
const SHEET_SIZES = ["peek", "half", "full"];

function setSheet(size) {
  panel.dataset.sheet = size;
  setTimeout(fitRoute, 280);
}

function stepSheet(direction) {
  const i = SHEET_SIZES.indexOf(panel.dataset.sheet);
  setSheet(SHEET_SIZES[Math.min(Math.max(i + direction, 0), SHEET_SIZES.length - 1)]);
}

// Drag the handle up or down, or tap it to cycle through the sizes
let dragStartY = null;
$("sheet-handle").addEventListener("pointerdown", (e) => { dragStartY = e.clientY; });
$("sheet-handle").addEventListener("pointerup", (e) => {
  if (dragStartY === null) return;
  const moved = e.clientY - dragStartY;
  dragStartY = null;
  if (moved < -30) stepSheet(1);
  else if (moved > 30) stepSheet(-1);
  else setSheet(panel.dataset.sheet === "full" ? "peek" : SHEET_SIZES[SHEET_SIZES.indexOf(panel.dataset.sheet) + 1]);
});

// ------------------------------------------------------------------- map
let map;
let routeLayer;
let focusMarker;
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function initMap() {
  if (!window.L) {
    $("map").textContent = "The map could not load. Check your connection.";
    return;
  }
  map = L.map("map", { zoomControl: false }).setView([12.9, 121.8], 6); // the Philippines
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  routeLayer = L.layerGroup().addTo(map);
  // Leaflet needs to hear when its box changes size (window resize, phone rotation)
  new ResizeObserver(() => map.invalidateSize()).observe($("map"));

  // Start centered in the part of the map the panel does not cover
  const box = panel.getBoundingClientRect();
  map.panBy(isPhone() ? [0, (window.innerHeight - box.top) / 2] : [-box.right / 2, 0], { animate: false });
}

let routeBounds = null;

// Fit the route into the part of the map the panel and chips do not cover
function fitRoute() {
  if (!map || !routeBounds) return;
  const box = panel.getBoundingClientRect();
  const options = isPhone()
    ? { paddingTopLeft: [24, 116], paddingBottomRight: [24, window.innerHeight - box.top + 24] }
    : { paddingTopLeft: [document.body.classList.contains("panel-hidden") ? 40 : box.right + 40, 72],
        paddingBottomRight: [72, 96] };
  map.fitBounds(routeBounds, options);
}

const stopsKey = (stops) => stops.map((s) => s.name).join("|");

// Lettered pins for the stops; returns their bounds
function drawPins(stops) {
  const last = stops.length - 1;
  stops.forEach((stop, i) => {
    const pin = L.divIcon({
      className: i === last ? "map-pin end" : "map-pin",
      html: `<span>${letter(i)}</span>`, // only a generated letter goes into HTML
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    });
    L.marker([stop.lat, stop.lng], { icon: pin })
      .bindTooltip(el("span", { textContent: `${letter(i)}. ${stop.name}` }))
      .addTo(routeLayer);
  });
  return L.latLngBounds(stops.map((s) => [s.lat, s.lng]));
}

function clearMap() {
  routeLayer.clearLayers();
  if (focusMarker) focusMarker.remove();
}

function drawRoute(route) {
  if (!map) return;
  clearMap();
  // a wider line underneath makes the route stand out on any background
  L.polyline(route.line, { color: cssVar("--route-casing"), weight: 9, opacity: 0.9 }).addTo(routeLayer);
  const line = L.polyline(route.line, { color: cssVar("--accent"), weight: 5 }).addTo(routeLayer);
  drawPins(route.stops);
  routeBounds = line.getBounds();
  fitRoute();
}

// Compare: every mode's route at once, faded until highlighted
let compareLines = {};

function drawCompare(c) {
  if (!map) return;
  clearMap();
  compareLines = {};
  let bounds = null;
  Object.entries(c.lines || {}).forEach(([label, points]) => { // older saved results have no lines
    if (!points) return; // that mode has no route
    const line = L.polyline(points, { color: cssVar(MODE_COLORS[label]), weight: 4, opacity: 0.55 })
      .bindTooltip(label, { sticky: true })
      .on("click", () => selectCompare(label))
      .addTo(routeLayer);
    compareLines[label] = line;
    bounds = bounds ? bounds.extend(line.getBounds()) : line.getBounds();
  });
  const pinBounds = drawPins(c.stops);
  routeBounds = bounds || pinBounds;
  fitRoute();
}

// Highlight one mode in Compare: its line, its card and the summary chip
function selectCompare(label) {
  const pick = lastCompare && lastCompare.modes.find((m) => m.Mode === label && m.Minutes !== null);
  comparePick = pick ? label : null;
  highlightLine(comparePick);
  document.querySelectorAll(".mode-card").forEach((card) => {
    const picked = card.dataset.mode === comparePick;
    card.classList.toggle("selected", picked);
    if (card.getAttribute("role")) card.setAttribute("aria-pressed", picked);
  });
  if (!pick) {
    $("summary").hidden = true;
    return;
  }
  const currency = $("currency").value.trim() || "PHP";
  showSummary([
    [MODE_ICONS[MODE_KEYS[label]], label],
    ["route", `${fmt(pick.Distance)} ${lastCompare.unit}`],
    ["clock", pick.Time],
    pick["Fuel cost"] ? ["fuel", `${currency} ${fmt(pick["Fuel cost"], 2)}`] : ["flame", `${fmt(pick["Calories (kcal)"], 0)} kcal`],
  ]);
}

function highlightLine(label) {
  Object.entries(compareLines).forEach(([name, line]) => {
    const picked = name === label;
    line.setStyle({ weight: picked ? 7 : 4, opacity: picked ? 1 : 0.55 });
    if (picked) line.bringToFront();
  });
}

function focusStep(step, button) {
  if (!map) return;
  document.querySelectorAll(".step-btn.active").forEach((b) => b.classList.remove("active"));
  button.classList.add("active");
  if (focusMarker) focusMarker.remove();
  focusMarker = L.circleMarker([step.lat, step.lon], {
    radius: 10, color: cssVar("--accent"), weight: 3, fillColor: cssVar("--surface"), fillOpacity: 1,
  }).bindTooltip(el("span", { textContent: step.Direction }), { permanent: true, direction: "top", offset: [0, -10] })
    .addTo(map);

  // Center the step in the visible part of the map, not behind the panel
  // (the map's center moves left of the step on desktop, below it on phones)
  const box = panel.getBoundingClientRect();
  const offset = isPhone() ? L.point(0, (window.innerHeight - box.top) / 2)
    : L.point(document.body.classList.contains("panel-hidden") ? 0 : -box.right / 2, 0);
  const zoom = 16;
  const center = map.project([step.lat, step.lon], zoom).add(offset);
  map.flyTo(map.unproject(center, zoom), zoom, { duration: 0.6 });
}

function showSummary(parts) {
  $("summary").replaceChildren(...parts.map(([iconName, text]) => el("span", {}, icon(iconName), text)));
  $("summary").hidden = false;
}

// ------------------------------------------------------------- rendering
const fmt = (n, digits = 1) =>
  Number(n).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });

// One column of the stats strip: label, big value, and a small detail line
function metric(iconName, label, value, detail) {
  return el("div", { className: "metric" },
    el("span", { className: "metric-label" }, icon(iconName), label),
    el("strong", { textContent: value, title: value }),
    el("span", { className: "metric-detail", textContent: detail }));
}

// Pick a turn arrow from the instruction text GraphHopper sends
function turnIcon(text) {
  const t = text.toLowerCase();
  if (t.startsWith("arrive")) return "flag";
  if (t.includes("waypoint")) return "pin";
  if (t.includes("u-turn")) return "uturn";
  if (t.includes("roundabout")) return "roundabout";
  if (t.includes("left")) return "left";
  if (t.includes("right")) return "right";
  return "straight";
}

let lastSteps = [];

// The three numbers on the map's summary chip
function routeSummary(r) {
  const currency = $("currency").value.trim() || "PHP";
  return [
    ["route", `${fmt(r.distance)} ${r.unit}`],
    ["clock", r.time_text],
    r.fuel_cost !== undefined ? ["fuel", `${currency} ${fmt(r.fuel_cost, 2)}`] : ["flame", `${fmt(r.calories_kcal, 0)} kcal`],
  ];
}

function renderRoute(r) {
  const currency = $("currency").value.trim() || "PHP";
  const driving = r.fuel_cost !== undefined;
  $("metrics").replaceChildren(
    metric("route", "Distance", `${fmt(r.distance)} ${r.unit}`, `${r.stops.length} stops`),
    metric("clock", "Time", r.time_text, r.mode),
    driving
      ? metric("fuel", "Gas cost", `${currency} ${fmt(r.fuel_cost, 2)}`,
               r.people > 1 ? `${currency} ${fmt(r.cost_per_person, 2)} each` : `${fmt(r.liters)} liters`)
      : metric("flame", "Calories", `${fmt(r.calories_kcal, 0)} kcal`, "estimate"));
  // only calories need a caveat; everything else fits in the strip
  $("metric-note").textContent = driving ? ""
    : "Calories are estimated from your weight and average speed; real burn varies with fitness, hills and wind.";
  $("metric-note").hidden = driving;

  // Stops with the leg between each pair
  const last = r.stops.length - 1;
  const rows = [];
  r.stops.forEach((stop, i) => {
    rows.push(el("li", { className: "place" },
      el("span", { className: i === last ? "pin end" : "pin", textContent: letter(i) }),
      el("div", {},
        el("strong", { textContent: stop.name }),
        el("span", { className: "muted", textContent: `You typed "${stop.query}"${stop.type ? ` · ${stop.type}` : ""}` }))));
    const leg = r.legs[i];
    if (i < last && leg) {
      rows.push(el("li", { className: "leg" }, el("span", { textContent: `${fmt(leg.Distance)} ${r.unit} · ${leg.Time}` })));
    }
  });
  $("timeline").replaceChildren(...rows);

  lastSteps = r.steps;
  $("steps").replaceChildren(...r.steps.map((step) => {
    const button = el("button", { type: "button", className: "step-btn" },
      el("span", { className: "turn" }, icon(turnIcon(step.Direction))),
      el("span", { className: "step-text", textContent: step.Direction }),
      el("span", { className: "step-meta", textContent: `${fmt(step.Distance, 2)} ${r.unit} · ${step.Time}` }));
    button.addEventListener("click", () => focusStep(step, button));
    return el("li", {}, button);
  }));

  lastRoute = r;
  enableTab("route");
  showTab("route"); // draws the route and its summary
  if (isPhone() && panel.dataset.sheet === "peek") setSheet("half");
}

function renderCompare(c) {
  const currency = $("currency").value.trim() || "PHP";
  const ok = c.modes.filter((m) => m.Minutes !== null);
  const slowest = Math.max(...ok.map((m) => m.Minutes), 1);

  $("compare-cards").replaceChildren(...c.modes.map((m) => {
    const mode = MODE_KEYS[m.Mode];
    const failed = m.Minutes === null;
    const best = m.Mode === c.fastest;
    const detail = failed ? null
      : m["Fuel cost"] ? `${fmt(m.Distance)} ${c.unit} · ${currency} ${fmt(m["Fuel cost"], 2)} gas`
      : `${fmt(m.Distance)} ${c.unit} · ${fmt(m["Calories (kcal)"], 0)} kcal`;

    // Clicking a card highlights its line; "Directions" opens its full route
    const directions = !failed && el("button", { type: "button", className: "btn ghost small", textContent: "Directions" });
    const card = el("div", { className: `mode-card${best ? " best" : ""}${failed ? " failed" : ""}`, style: `--mode-color: var(${MODE_COLORS[m.Mode]})` },
      el("span", { className: "mode-card-head" }, icon(MODE_ICONS[mode]), m.Mode, best && el("span", { className: "badge", textContent: "Fastest" })),
      el("span", { className: "mode-time", textContent: m.Time }),
      failed
        ? el("span", { className: "mode-reason", textContent: c.errors[m.Mode] || "No route" })
        : el("span", { className: "mode-detail", textContent: detail }),
      !failed && el("div", { className: "mode-foot" },
        el("span", { className: "meter" }, el("span", { style: `width:${(m.Minutes / slowest) * 100}%` })),
        directions));
    card.dataset.mode = m.Mode;

    if (!failed) {
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.addEventListener("click", () => selectCompare(m.Mode));
      card.addEventListener("keydown", (e) => {
        if (e.target === card && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); selectCompare(m.Mode); }
      });
      directions.addEventListener("click", (e) => {
        e.stopPropagation();
        document.querySelector(`input[name="mode"][value="${mode}"]`).checked = true;
        saveForm();
        $("get-route").click();
      });
    }
    return card;
  }));

  $("compare-unit").textContent = `Distances in ${c.unit === "mi" ? "miles" : "kilometers"}`;
  // A route for other stops would be out of date next to these results
  if (lastRoute && stopsKey(lastRoute.stops) !== stopsKey(c.stops)) {
    lastRoute = null;
    document.querySelector('.tab[data-tab="route"]').disabled = true;
  }
  lastCompare = c;
  comparePick = c.fastest;
  enableTab("compare");
  showTab("compare"); // draws every mode's line, the fastest highlighted
  if (isPhone() && panel.dataset.sheet === "peek") setSheet("half");

  const failed = Object.keys(c.errors);
  if (failed.length) toast(`No route for ${failed.join(" and ")} on this trip.`, "warn");
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

initMap();
if (!currentKey()) keyDialog.showModal(); // first visit: ask for the key right away
