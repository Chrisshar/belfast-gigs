// Shared by the hero prototypes: the approved Index renderers, plus helpers for hero data.
document.addEventListener("DOMContentLoaded", () => {
  const mark = document.querySelector("#mark");
  if (mark) mark.innerHTML = logoMark("cranes");
});

const DESIGN = {
  recent: (g) => { const p = parts(g.date); return `<a class="card" href="#"><div class="art">${instrument(g.genres, { shape: "banner" })}</div><div class="body"><div class="d">${p.dow} ${p.day} ${p.mon}${g.time ? ", " + g.time : ""}</div><h3>${esc(g.headliner)}</h3><div class="v">${esc(g.venue)}</div></div></a>`; },
  card: (g) => `<a class="row" href="#"><div class="art">${instrument(g.genres)}</div><div><h3>${esc(g.headliner)}</h3>${g.support.length ? `<div class="sup">with ${esc(g.support.join(", "))}</div>` : ""}<div class="meta"><b>${esc(g.venue)}</b>${g.room ? " · " + esc(g.room) : ""}${g.time ? " · " + g.time : ""}${g.genres.length ? " · " + g.genres.map(esc).join(", ") : ""}</div></div><div class="price">${price(g)}${STATUS[g.status] ? `<small>${STATUS[g.status]}</small>` : ""}</div></a>`,
  day: (p, cards) => `<div class="day"><div class="date"><div class="n">${p.day}</div><div class="w">${p.dow}</div></div><div>${cards}</div></div>`,
  month: (p, days) => `<h3 class="month">${p.monLong} ${p.year}</h3>${days}`,
  detail: () => "",
};

// Hero data, from the same sample and "today" as the listing.
function upcomingWithin(days) {
  const end = addDays(TODAY, days);
  return GIGS.filter((g) => g.date >= TODAY && g.date <= end);
}
function genreCounts() {
  const counts = new Map();
  for (const g of GIGS) for (const genre of g.genres) counts.set(genre, (counts.get(genre) || 0) + 1);
  return [...counts].sort((a, b) => b[1] - a[1]);
}
