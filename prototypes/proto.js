// Shared by the three design prototypes: sample data helpers + working filters.
// Each page defines DESIGN = { card, recent, day, month, detail } returning HTML strings.
const TODAY = "2026-10-25";
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DOW_LONG = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MON_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function parts(date) {
  const x = new Date(date + "T12:00:00Z");
  return { dow: DOW[x.getUTCDay()], dowLong: DOW_LONG[x.getUTCDay()], day: x.getUTCDate(), mon: MON[x.getUTCMonth()], monLong: MON_LONG[x.getUTCMonth()], year: x.getUTCFullYear() };
}
function addDays(date, n) {
  const x = new Date(date + "T12:00:00Z");
  x.setUTCDate(x.getUTCDate() + n);
  return x.toISOString().slice(0, 10);
}
function price(g) {
  if (g.price == null) return "";
  return "£" + (Number.isInteger(g.price) ? g.price : g.price.toFixed(2));
}
const STATUS = { sold_out: "Sold out", cancelled: "Cancelled", postponed: "Postponed", rescheduled: "Rescheduled" };
function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

const state = { venue: "", genres: new Set(), quick: "", month: "" };

function quickRange(q) {
  // TODAY is a Sunday in the sample; "this weekend" is the coming Fri-Sun.
  if (q === "tonight") return [TODAY, TODAY];
  if (q === "weekend") return [addDays(TODAY, 5), addDays(TODAY, 7)];
  if (q === "week") return [TODAY, addDays(TODAY, 7)];
  return null;
}

function matches(g) {
  if (state.venue && g.venue !== state.venue) return false;
  if (state.month && g.date.slice(0, 7) !== state.month) return false;
  if (state.genres.size && !g.genres.some((x) => state.genres.has(x))) return false;
  const r = quickRange(state.quick);
  if (r && (g.date < r[0] || g.date > r[1])) return false;
  return true;
}

function buildFilters() {
  const venues = [...new Set(GIGS.map((g) => g.venue))].sort();
  const months = [...new Set(GIGS.map((g) => g.date.slice(0, 7)))];
  const genres = [...new Set(GIGS.flatMap((g) => g.genres))].sort();
  document.querySelector("#filters").innerHTML = `
    <div class="quick">
      ${[["tonight", "Tonight"], ["weekend", "This weekend"], ["week", "Next 7 days"]].map(([k, l]) => `<button class="chip" data-quick="${k}">${l}</button>`).join("")}
      <button class="more" aria-expanded="false" aria-controls="filters-body">Filters</button>
    </div>
    <div class="filters-body" id="filters-body">
      <div class="selects">
        <label><span>Venue</span><select id="f-venue"><option value="">All venues</option>${venues.map((v) => `<option>${esc(v)}</option>`).join("")}</select></label>
        <label><span>Month</span><select id="f-month"><option value="">Any month</option>${months.map((m) => `<option value="${m}">${parts(m + "-01").monLong} ${m.slice(0, 4)}</option>`).join("")}</select></label>
      </div>
      <div class="genres">${genres.map((g) => `<button class="chip genre" data-genre="${esc(g)}">${esc(g)}</button>`).join("")}</div>
    </div>`;
  const more = document.querySelector("#filters .more");
  more.addEventListener("click", () => {
    const open = document.querySelector("#filters").classList.toggle("open");
    more.setAttribute("aria-expanded", String(open));
  });
  document.querySelectorAll("[data-quick]").forEach((b) =>
    b.addEventListener("click", () => {
      state.quick = state.quick === b.dataset.quick ? "" : b.dataset.quick;
      document.querySelectorAll("[data-quick]").forEach((x) => x.classList.toggle("on", x.dataset.quick === state.quick));
      render();
    }),
  );
  document.querySelectorAll("[data-genre]").forEach((b) =>
    b.addEventListener("click", () => {
      const g = b.dataset.genre;
      state.genres.has(g) ? state.genres.delete(g) : state.genres.add(g);
      b.classList.toggle("on");
      render();
    }),
  );
  document.querySelector("#f-venue").addEventListener("change", (e) => ((state.venue = e.target.value), render()));
  document.querySelector("#f-month").addEventListener("change", (e) => ((state.month = e.target.value), render()));
}

function render() {
  const list = GIGS.filter(matches);
  const recent = list.filter((g) => g.recent);
  document.querySelector("#recent").innerHTML = recent.length ? recent.map(DESIGN.recent).join("") : `<p class="empty">Nothing new matches.</p>`;
  const byMonth = new Map();
  for (const g of list) {
    const m = g.date.slice(0, 7);
    if (!byMonth.has(m)) byMonth.set(m, new Map());
    const days = byMonth.get(m);
    if (!days.has(g.date)) days.set(g.date, []);
    days.get(g.date).push(g);
  }
  document.querySelector("#upcoming").innerHTML = list.length
    ? [...byMonth].map(([m, days]) => DESIGN.month(parts(m + "-01"), [...days].map(([d, gigs]) => DESIGN.day(parts(d), gigs.map(DESIGN.card).join(""))).join(""))).join("")
    : `<p class="empty">No gigs match those filters.</p>`;
  document.querySelector("#count").textContent = `${list.length} gig${list.length === 1 ? "" : "s"}`;
}

window.addEventListener("DOMContentLoaded", () => {
  buildFilters();
  render();
  document.querySelector("#detail").innerHTML = DESIGN.detail(GIGS.find((g) => g.slug.includes("cleveland-watkiss")) || GIGS[0]);
  if (DESIGN.after) DESIGN.after();
});
