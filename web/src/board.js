/**
 * The sign face. Field order follows a real Bauschild: what is being built,
 * who is building it, who designed it, who runs the site, under which file
 * number — the sequence someone standing at the fence reads top to bottom.
 */

const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[character],
  );

const lengthBand = (value) => {
  if (value.length > 190) return "epic";
  if (value.length > 90) return "long";
  return "short";
};

const field = (label, value, { aside, modifier = "" } = {}) => {
  if (!value) return "";
  const band = ` data-length="${lengthBand(String(value))}"`;
  return `
    <div class="field">
      <div class="field__label">${escape(label)}</div>
      <p class="field__value ${modifier}"${band}>${escape(value)}</p>
      ${aside ? `<p class="field__aside">${escape(aside)}</p>` : ""}
    </div>`;
};

const party = (label, name, street, place, note) => {
  if (!name) return "";
  const lines = [street, place].filter(Boolean).join(", ");
  return field(label, name, { aside: [note, lines].filter(Boolean).join(" · ") });
};

export function renderBoard(mount, site) {
  const area = site.parcel_area
    ? `${site.parcel_area.toLocaleString("de-DE")} m²`
    : "";

  mount.parentElement.classList.remove("board--vacant");
  mount.innerHTML = `
    <div class="board__address">
      <h2 class="board__street">${escape(site.site_address)}</h2>
      <div class="board__parcel">
        ${escape(site.gemarkung_label ?? "")}<br />
        ${escape(area)}
      </div>
    </div>

    ${field("Bauvorhaben", site.description, { modifier: "field__value--display" })}
    ${party(
      "Bauherr",
      site.builder_name,
      site.builder_address,
      site.builder_location,
      site.represented_by,
    )}
    ${party(
      "Entwurfsverfasser",
      site.architect_name,
      site.architect_address,
      site.architect_location,
    )}
    ${party(
      "Bauleiter",
      site.site_manager_name,
      site.site_manager_address,
      site.site_manager_location,
    )}
    ${field("Aktenzeichen", site.permit_number, { modifier: "field__value--mono" })}
    ${field("Flurstück", site.parcel_info, { modifier: "field__value--mono" })}
    ${
      site.url
        ? `<a class="board__source" href="${escape(site.url)}">Schild bei der Bauaufsicht</a>`
        : ""
    }
  `;
}

/** The page's own sign, shown until a permit is picked. */
export function renderVacantBoard(mount, count) {
  mount.parentElement.classList.add("board--vacant");
  mount.innerHTML = `
    <div class="board__address">
      <h2 class="board__street">Karte aller Bauschilder</h2>
      <div class="board__parcel">Frankfurt<br />am Main</div>
    </div>

    ${field("Bauvorhaben", "Jedes genehmigte Bauschild der Stadt an seinem Flurstück", {
      modifier: "field__value--display",
    })}
    ${field("Bauherr", "Bauaufsicht Frankfurt am Main", {
      aside: "öffentliches Register",
    })}
    ${field("Flurstücke", "Stadtvermessungsamt Frankfurt am Main", {
      aside: "ALKIS-Liegenschaftskataster",
    })}
    ${field("Bestand", `${count.toLocaleString("de-DE")} Schilder`, {
      modifier: "field__value--mono",
    })}

    <p class="board__hint">
      Ein Schild auf der Karte anklicken, um es zu lesen.
      Ab Zoomstufe 15 stehen die Schilder selbst in der Karte.
    </p>
  `;
}

export function renderResults(mount, matches, sites) {
  if (!matches.length) {
    mount.innerHTML = `<div class="results__count">Keine Treffer</div>`;
    return;
  }

  const shown = matches.slice(0, 60);
  const rows = shown
    .map((index) => {
      const site = sites[index];
      return `
        <button class="result" type="button" data-index="${index}">
          <span class="result__street">${escape(site.site_address)}</span>
          <span class="result__what">${escape(site.description ?? "")}</span>
        </button>`;
    })
    .join("");

  const label =
    matches.length > shown.length
      ? `${matches.length} Treffer · erste ${shown.length}`
      : `${matches.length} ${matches.length === 1 ? "Treffer" : "Treffer"}`;

  mount.innerHTML = `<div class="results__count">${label}</div>${rows}`;
}
