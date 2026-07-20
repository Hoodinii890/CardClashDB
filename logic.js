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
  buffsInput: "buffs",
  supportedCardToggle: "support"
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
  container.innerHTML = `<p class="status-msg">Searching cards...</p>`;

  // Cambia el orden: ahora es por card_name ascendente
  let url = `${SUPABASE_URL}/rest/v1/Cards?select=*&order=card_name.asc`;

  for (const [inputId, column] of Object.entries(FIELD_MAP)) {
    const value = document.getElementById(inputId).value.trim();
    if (value) {
      switch (column) {
        case "revive":
          if (value === "Si") { // "Si" means Yes, if your app input is in English, change this to "Yes"
            url += `&${column}=not.is.null`;
          } else if (value === "No") {
            url += `&${column}=is.null`;
          } else {
            url += `&${column}=ilike.**`;
          }
          break;
        case "role_rating":
          // value llega como 0, 1, ... 10
          if (value === "0") {
            // filtrar desde 0/10 hasta 0.9/10
            url += `&or=(role_rating.ilike.0/10*,role_rating.ilike.0.1/10*,role_rating.ilike.0.2/10*,role_rating.ilike.0.3/10*,role_rating.ilike.0.4/10*,role_rating.ilike.0.5/10*,role_rating.ilike.0.6/10*,role_rating.ilike.0.7/10*,role_rating.ilike.0.8/10*,role_rating.ilike.0.9/10*)`;
          } else if (value === "10") {
            url += `&${column}=ilike.10/10*`;
          } else if (!isNaN(Number(value)) && Number(value) >= 1 && Number(value) <= 19) {
            // Si es número, filtra role_rating que empieza exactamente por el número seguido de "/10" o por ese número un punto decimal seguido de "/10"
            // Ejemplo: 1 busca 1/10, 1.1/10, 1.2/10, ..., 1.9/10, 1.0/10 (solo para enteros)
            if (value.includes(".")) {
              // Si es decimal, busca p.ej. "1.5/10"
              url += `&${column}=ilike.${encodeURIComponent(value)}/10*`;
            } else {
              // Si es entero, busca "1/10" exactamente y "1.0/10", "1.1/10", ..., "1.9/10"
              const ors = [];
              ors.push(`${column}.ilike.${encodeURIComponent(value)}/10*`);
              for (let i = 0; i <= 9; ++i) {
                ors.push(`${column}.ilike.${encodeURIComponent(value)}.${i}/10*`);
              }
              url += `&or=(${ors.join(",")})`;
            }
          } else {
            url += `&${column}=ilike.*${encodeURIComponent(value)}*`;
          }
          break;
        default:
          url += `&${column}=ilike.*${encodeURIComponent(value)}*`;
          break;
      }
    } else {
      if (column == "support") {
        // Valida el estado del botón (clase .prompt-active = activo)
        const supportBtn = document.getElementById('supportedCardToggle');
        const supportActive = supportBtn && supportBtn.classList.contains('prompt-active');
        if (supportActive) {
          // Si el toggle está activo ("Support"), busca donde "support" es nulo
          url += `&${column}=not.is.null&${column}=neq.false`;
        } else {
          // Si no está activo ("Cards"), busca donde "support" es no nulo
          url += `&or=(${column}.is.null,${column}.eq.false)`;
        }
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
      throw new Error(errBody?.message || `Error ${res.status} when querying Supabase`);
    }

    const data = await res.json();

    if (!Array.isArray(data)) {
      throw new Error("The API response format was not as expected.");
    }

    renderResults(data);
  } catch (err) {
    container.innerHTML = `<p class="status-msg status-error">${escapeHtml(err.message)}</p>`;
    console.error("Error in searchCards:", err);
  }
}

function renderResults(cards) {
  const container = document.getElementById("results");
  container.innerHTML = "";

  if (cards.length === 0) {
    container.innerHTML = `<p class="status-msg">No cards found with these filters.</p>`;
    return;
  }

  const countLabel = document.createElement("p");
  countLabel.className = "results-count";
  countLabel.textContent = `${cards.length} card${cards.length === 1 ? "" : "s"} found`;
  container.appendChild(countLabel);

  const list = document.createElement("ul");
  list.className = "card-grid";

  cards.forEach(card => list.appendChild(buildCard(card)));

  container.appendChild(list);
}

function buildCard(card) {
  // Border definitions, now each with a border, multiplier, color, css, background, and optional gradient
  const BORDERS = [
    { 
      border: "Basic", 
      multiplier: 1, 
      color: "#bbb", 
      css: "1.7px solid #bbb", 
      background: "#171d29"
    },
    { 
      border: "Gold", 
      multiplier: 4, 
      color: "#FFD700", 
      css: "2.5px solid #FFD700", 
      background: "#18151a"
    },
    { 
      border: "Rainbow", 
      multiplier: 16, 
      color: "rainbow", 
      css: "3px solid", 
      gradient: true,
      background: "#232442"
    },
    { 
      border: "Secret", 
      multiplier: 64, 
      color: "#d42c26", 
      css: "3px solid #d42c26", 
      background: "linear-gradient(135deg, #270813 0%, #43081e 40%, #14020b 100%)"
    }
  ];

  // Helper to get border style
  function getBorderStyle(borderName) {
    const border = BORDERS.find(b => b.border === borderName);
    if (!border)
      return BORDERS[0];
    return border;
  }

  // Helper for gradient borders (rainbow)
  function applyGradientBorder(element, background) {
    element.style.border = "3px solid transparent";
    element.style.background = 
      `linear-gradient(${background}, ${background}) padding-box, linear-gradient(90deg, red, orange, yellow, green, blue, indigo, violet, red) border-box`;
    element.style.backgroundOrigin = "border-box";
    element.style.backgroundClip = "padding-box, border-box";
  }

  let selectedBorder = BORDERS[0]; // Default to Basic

  const li = document.createElement("li");
  li.className = "card";
  li.style.transition = "border 0.2s";

  // Check if support is active for this card
  const isSupport = card.support === true || card.support === "true";

  // Apply border/background logic
  if (selectedBorder.gradient) {
    applyGradientBorder(li, selectedBorder.background);
  } else if (selectedBorder.background && selectedBorder.background.startsWith("linear-gradient")) {
    li.style.border = selectedBorder.css;
    li.style.background = selectedBorder.background;
    li.style.backgroundClip = "";
    li.style.backgroundOrigin = "";
  } else {
    li.style.border = selectedBorder.css;
    li.style.background = selectedBorder.background || "";
    li.style.backgroundClip = "";
    li.style.backgroundOrigin = "";
  }

  const ratingShort = extractRatingShort(card.role_rating);

  const top = document.createElement("div");
  top.className = "card-top";
  top.innerHTML = `
    <div class="card-heading">
      <img class="card-icon" src="${card.icon ? escapeHtml(card.icon) : "https://static.thenounproject.com/png/1318110-200.png"}" alt="Card icon" style="width: 80px; height: 100px; object-fit: cover; margin-right: 0.5em; vertical-align: middle; border: 2px solid #c19a49; border-radius: 6px;" />
      <p class="card-name" style="display: inline;"></p>
    </div>
    ${ratingShort ? `<span class="rating-badge"></span>` : ""}
  `;
  top.querySelector(".card-name").textContent = card.card_name || "Unnamed card";
  if (ratingShort) top.querySelector(".rating-badge").textContent = ratingShort;
  li.appendChild(top);

  // New row for role/support/fusion labels
  const lowerRoleRow = document.createElement("div");
  lowerRoleRow.className = "card-roles-row";
  lowerRoleRow.style.display = "flex";
  lowerRoleRow.style.flexWrap = "wrap";
  lowerRoleRow.style.gap = "0.45em";
  lowerRoleRow.style.marginTop = "0.3em";
  lowerRoleRow.style.marginBottom = "0.2em";
  lowerRoleRow.style.alignItems = "center";
  
  // -- Main role badge (if present)
  if (isSupport) {
    // Procesar los roles: split, quitar vacíos y trims
    let roles = (card.role || "")
      .split(/\s*\/\s*/)
      .map(r => r.trim())
      .filter(Boolean);

    // Filtrar los roles que NO son exactamente "Support"
    let displayRoles = roles.filter(r => r !== "Support");

    // Si hay algún otro rol además de "Support" o nombres compuestos, mostrarlo
    displayRoles.forEach(role => {
      const roleSpan = document.createElement("span");
      roleSpan.className = "role";
      roleSpan.textContent = role;
      lowerRoleRow.appendChild(roleSpan);
    });
  }else{
    const roleSpan = document.createElement("span");
    roleSpan.className = "role";
    roleSpan.textContent = card.role;
    lowerRoleRow.appendChild(roleSpan);
  }

  // -- Support flag as badge-style but blue/green
  if (isSupport) {
    const supportSpan = document.createElement("span");
    supportSpan.className = "role";
    supportSpan.textContent = "Support";
    supportSpan.style.background = "#23bda7";
    supportSpan.style.color = "#fff";
    lowerRoleRow.appendChild(supportSpan);
  }

  // -- Fusion badge (if present) -- unique color
  if (card.fusion != null) {
    const fusionSpan = document.createElement("span");
    fusionSpan.className = "role";
    fusionSpan.textContent = "Fusion";
    fusionSpan.style.background = "linear-gradient(90deg, #6d52ed 40%, #63dee7 100%)";
    fusionSpan.style.color = "#fff";
    lowerRoleRow.appendChild(fusionSpan);
  }
  if (card.revive != null) {
    const fusionSpan = document.createElement("span");
    fusionSpan.className = "role";
    fusionSpan.textContent = "Revive";
    fusionSpan.style.background = "linear-gradient(90deg, #3791b5 20%, #19b15c 80%)";
    fusionSpan.style.color = "#fff";
    lowerRoleRow.appendChild(fusionSpan);
  }
  if (card.summons != null) {
    const summonsSpan = document.createElement("span");
    summonsSpan.className = "role";
    summonsSpan.textContent = "Summoner";
    // Unique color palette for summon badge
    summonsSpan.style.background = "linear-gradient(90deg, #f27a1a 35%, #ffda56 100%)";
    summonsSpan.style.color = "#222";
    lowerRoleRow.appendChild(summonsSpan);
  }

  if (lowerRoleRow.children.length === 0) {
    lowerRoleRow.style.height = "1.5em";
  }
  li.appendChild(lowerRoleRow);

  // Border select: now, only if NOT Support card
  let statsAnchor = null;
  let borderSelectWrap, borderSelect;

  if (!isSupport) {
    borderSelectWrap = document.createElement("div");
    borderSelectWrap.style.display = "flex";
    borderSelectWrap.style.alignItems = "center";
    borderSelectWrap.style.margin = "0.25em 0 0.4em 0";
    borderSelectWrap.style.gap = "0.5em";

    const borderLabel = document.createElement("label");
    borderLabel.textContent = "Border: ";
    borderLabel.className = "ability-name";
    borderLabel.style.fontSize = "0.92em";
    borderSelectWrap.appendChild(borderLabel);

    borderSelect = document.createElement("select");
    BORDERS.forEach(borderObj => {
      const opt = document.createElement("option");
      opt.value = borderObj.border;
      opt.textContent = borderObj.border;
      borderSelect.appendChild(opt);
    });
    borderSelect.value = selectedBorder.border;

    borderSelectWrap.appendChild(borderSelect);
    li.appendChild(borderSelectWrap);
  }

  // -- add abilities and desc
  if (card.ability_name) {
    const abilityName = document.createElement("p");
    abilityName.className = "ability-name";
    abilityName.textContent = card.ability_name;
    li.appendChild(abilityName);
    statsAnchor = abilityName;
  }

  if (card.ability_description) {
    const abilityDesc = document.createElement("p");
    abilityDesc.className = "ability-desc";
    abilityDesc.textContent = card.ability_description;
    li.appendChild(abilityDesc);
    statsAnchor = abilityDesc;
  }

  // Si no hay abilities/desc, nuestro anchor será el border select, pero solo si existe (sólo no-support)
  if (!statsAnchor && borderSelectWrap) statsAnchor = borderSelectWrap;

  // Mostrar el título y las stats en una sola fila debajo de los abilities (o border select) y SIEMPRE ANTES de details
  let statsRow;
  function renderStats() {
    if (statsRow) statsRow.remove();
    // Si es support, NO mostrar stats ni el label
    if (isSupport) {
      return;
    }
    if (card.stats && (card.stats.DMG !== undefined || card.stats.HP !== undefined)) {
      statsRow = document.createElement("div");
      statsRow.className = "stat-row-title";
      statsRow.style.display = "flex";
      statsRow.style.alignItems = "center";
      statsRow.style.gap = "1.2em";

      // Título/heading para las stats base (en la row)
      const statsTitle = document.createElement("span");
      statsTitle.className = "stat-block-title ability-name";
      statsTitle.textContent = "Base stats: ";
      statsTitle.style.fontWeight = "bold";
      statsTitle.style.fontSize = "0.98em";
      statsRow.appendChild(statsTitle);

      // Stats (en la misma row)
      const statsValues = document.createElement("span");
      let statsHtml = "";
      // apply multiplier (in support, no border select available, so always 1)
      const mul = (!isSupport && selectedBorder && selectedBorder.multiplier) ? selectedBorder.multiplier : 1;
      if (card.stats.DMG !== undefined) {
        statsHtml += `<span class="dmgtag" style="color: #d12828;font-weight:500;">DMG</span> <strong>${(card.stats.DMG * mul).toLocaleString()}</strong> `;
      }
      if (card.stats.HP !== undefined) {
        statsHtml += `<span class="hptag" style="color: #209b4b;font-weight:500;margin-left:1em;">HP</span> <strong>${(card.stats.HP * mul).toLocaleString()}</strong>`;
      }
      statsValues.innerHTML = statsHtml;
      statsValues.style.marginLeft = "auto";
      statsValues.style.display = "flex";
      statsValues.style.gap = "0.4em";
      statsRow.appendChild(statsValues);

      // Insert always right after statsAnchor (if present) or at end
      if (statsAnchor && statsAnchor.parentNode === li) {
        li.insertBefore(statsRow, statsAnchor.nextSibling);
      } else {
        li.appendChild(statsRow);
      }
    }
  }

  // Handler for border select changes, only if present (no support)
  if (borderSelect) {
    borderSelect.addEventListener("change", () => {
      selectedBorder = getBorderStyle(borderSelect.value);

      if (selectedBorder.gradient) {
        applyGradientBorder(li, selectedBorder.background);
      } else if (selectedBorder.background && selectedBorder.background.startsWith("linear-gradient")) {
        li.style.border = selectedBorder.css;
        li.style.background = selectedBorder.background;
        li.style.backgroundClip = "";
        li.style.backgroundOrigin = "";
      } else {
        li.style.border = selectedBorder.css;
        li.style.background = selectedBorder.background || "";
        li.style.backgroundClip = "";
        li.style.backgroundOrigin = "";
      }
      renderStats();
    });
  }

  // Render stats the first time
  renderStats();

  // Add effect rows for the details section, as before
  const effectRows = [
    { label: "Buffs", value: card.buffs, cls: "tag-buff" },
    { label: "Debuffs", value: card.debuffs, cls: "tag-debuff" },
    { label: "Status effects", value: card.status_effects, cls: "tag-status" },
    { label: "Counters", value: card.counters, cls: "tag-counter" },
    { label: "Revive", value: card.revive, cls: "tag-revive" },
    { label: "Fusion", value: card.fusion, cls: "tag-fusion" },
    { label: "Summons", value: card.summons, cls: "tag-summon" },
    { label: "Caps", value: card.caps, cls: "tag-caps" },
  ].filter(row => row.value);

  if (effectRows.length || card.role_rating) {
    const details = document.createElement("details");
    details.className = "card-details";

    const summary = document.createElement("summary");
    summary.textContent = "View full card details";
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
      dt.textContent = "Analysis";
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