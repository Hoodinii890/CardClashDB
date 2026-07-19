const SUPABASE_URL = "https://bayhvosbgkptsrstwlkc.supabase.co";
const ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJheWh2b3NiZ2twdHNyc3R3bGtjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQzODIwNzgsImV4cCI6MjA5OTk1ODA3OH0.SgQMp56u4wDN_QdpBgVO8Cx4on6vrzS_VvXgFr_phdk";

const FIELD_MAP = {
  nameInput: "card_name",
  abilityInput: "ability_name",
  descInput: "ability_description",
  roleInput: "role",
  ratingInput: "role_rating",
  reviveInput: "revive",
  statusInput: "status_effects",
  debuffsInput: "debuffs",
  countersInput: "counters",
  buffsInput: "buffs"
};

document.addEventListener("DOMContentLoaded", () => {
  searchCards();

  document.querySelectorAll(".filter-field input").forEach(input => {
    input.addEventListener("keydown", e => {
      if (e.key === "Enter") searchCards();
    });
  });

  const clearBtn = document.getElementById("clearFiltersBtn");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      Object.keys(FIELD_MAP).forEach(id => {
        document.getElementById(id).value = "";
      });
      searchCards();
    });
  }
});

async function searchCards() {
  const container = document.getElementById("results");
  container.innerHTML = `<p class="status-msg">Buscando cartas...</p>`;

  let url = `${SUPABASE_URL}/rest/v1/Cards?select=*&order=id.asc`;

  for (const [inputId, column] of Object.entries(FIELD_MAP)) {
    const value = document.getElementById(inputId).value.trim();
    if (value) {
      switch (column) {
        case "revive":
          if (value === "Si") {
            url += `&${column}=not.is.null`;
          } else if (value === "No") {
            url += `&${column}=is.null`;
          } else {
            url += `&${column}=ilike.**`;
          }
          break;
        case "role_rating":
          url += `&${column}=ilike.${encodeURIComponent(value)}*`;
          break;
        default:
          url += `&${column}=ilike.*${encodeURIComponent(value)}*`;
          break;
      }
    }
  }

  try {
    const res = await fetch(url, {
      headers: {
        apikey: ANON_KEY,
        Authorization: `Bearer ${ANON_KEY}`
      }
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => null);
      throw new Error(errBody?.message || `Error ${res.status} al consultar Supabase`);
    }

    const data = await res.json();

    if (!Array.isArray(data)) {
      throw new Error("La respuesta de la API no tiene el formato esperado.");
    }

    renderResults(data);
  } catch (err) {
    container.innerHTML = `<p class="status-msg status-error">${escapeHtml(err.message)}</p>`;
    console.error("Error en searchCards:", err);
  }
}

function renderResults(cards) {
  const container = document.getElementById("results");
  container.innerHTML = "";

  if (cards.length === 0) {
    container.innerHTML = `<p class="status-msg">No se encontraron cartas con esos filtros.</p>`;
    return;
  }

  const countLabel = document.createElement("p");
  countLabel.className = "results-count";
  countLabel.textContent = `${cards.length} carta${cards.length === 1 ? "" : "s"} encontrada${cards.length === 1 ? "" : "s"}`;
  container.appendChild(countLabel);

  const list = document.createElement("ul");
  list.className = "card-grid";

  cards.forEach(card => list.appendChild(buildCard(card)));

  container.appendChild(list);
}

function buildCard(card) {
  const li = document.createElement("li");
  li.className = "card";

  const ratingShort = extractRatingShort(card.role_rating);

  const top = document.createElement("div");
  top.className = "card-top";
  top.innerHTML = `
    <div class="card-heading">
      <p class="card-name"></p>
      <span class="role"></span>
    </div>
    ${ratingShort ? `<span class="rating-badge"></span>` : ""}
  `;
  top.querySelector(".card-name").textContent = card.card_name || "Carta sin nombre";
  top.querySelector(".role").textContent = card.role || "Sin rol";
  if (ratingShort) top.querySelector(".rating-badge").textContent = ratingShort;
  li.appendChild(top);

  if (card.ability_name) {
    const abilityName = document.createElement("p");
    abilityName.className = "ability-name";
    abilityName.textContent = card.ability_name;
    li.appendChild(abilityName);
  }

  if (card.ability_description) {
    const abilityDesc = document.createElement("p");
    abilityDesc.className = "ability-desc";
    abilityDesc.textContent = card.ability_description;
    li.appendChild(abilityDesc);
  }

  const effectRows = [
    { label: "Buffs", value: card.buffs, cls: "tag-buff" },
    { label: "Debuffs", value: card.debuffs, cls: "tag-debuff" },
    { label: "Status effects", value: card.status_effects, cls: "tag-status" },
    { label: "Counters", value: card.counters, cls: "tag-counter" },
    { label: "Revive", value: card.revive, cls: "tag-revive" }
  ].filter(row => row.value);

  if (effectRows.length || card.role_rating) {
    const details = document.createElement("details");
    details.className = "card-details";

    const summary = document.createElement("summary");
    summary.textContent = "Ver ficha completa";
    details.appendChild(summary);

    const dl = document.createElement("dl");
    dl.className = "effect-list";

    effectRows.forEach(row => {
      const wrap = document.createElement("div");
      wrap.className = `effect-row ${row.cls}`;
      const dt = document.createElement("dt");
      dt.textContent = row.label;
      const dd = document.createElement("dd");
      dd.textContent = row.value;
      wrap.appendChild(dt);
      wrap.appendChild(dd);
      dl.appendChild(wrap);
    });

    if (card.role_rating) {
      const wrap = document.createElement("div");
      wrap.className = "effect-row tag-analysis";
      const dt = document.createElement("dt");
      dt.textContent = "Análisis";
      const dd = document.createElement("dd");
      dd.textContent = card.role_rating;
      wrap.appendChild(dt);
      wrap.appendChild(dd);
      dl.appendChild(wrap);
    }

    details.appendChild(dl);
    li.appendChild(details);
  }

  return li;
}

function extractRatingShort(roleRating) {
  if (!roleRating) return "";
  const match = roleRating.match(/^\s*([\d.]+\s*\/\s*\d+)/);
  return match ? match[1].replace(/\s+/g, "") : "";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}