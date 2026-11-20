import { useEffect, useState } from "react";
import api, { getApiError } from "../services/api";
import { Field } from "./ui";

/**
 * Cascading location dropdowns (campus > building > ... > room). Reports the selected
 * leaf id via onChange; `null` until the person has drilled down to a node with no children.
 */
export function LocationPicker({ value, onChange, error }) {
  const [levels, setLevels] = useState([]); // [{ options, selected }]
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let active = true;
    api
      .get("/reference/locations")
      .then(({ data }) => {
        if (active) setLevels([{ options: data, selected: "" }]);
      })
      .catch((e) => active && setLoadError(getApiError(e, "Could not load locations.")));
    return () => {
      active = false;
    };
  }, []);

  async function choose(levelIndex, id) {
    const kept = levels
      .slice(0, levelIndex + 1)
      .map((l, i) => (i === levelIndex ? { ...l, selected: id } : l));
    if (!id) {
      setLevels(kept);
      onChange(null);
      return;
    }
    try {
      const { data } = await api.get("/reference/locations", {
        params: { parent_id: id },
      });
      if (data.length) {
        setLevels([...kept, { options: data, selected: "" }]);
        onChange(null);
      } else {
        setLevels(kept);
        onChange(Number(id));
      }
    } catch (e) {
      setLoadError(getApiError(e, "Could not load locations."));
    }
  }

  return (
    <fieldset aria-describedby={error ? "location-error" : undefined}>
      <legend className="mb-1 text-sm font-medium text-slate-700">Location</legend>
      {loadError && <p className="field-error" role="alert">{loadError}</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        {levels.map((level, index) => (
          <Field key={index} label={index === 0 ? "Campus" : `Then choose (${index + 1})`} htmlFor={`loc-${index}`}>
            <select
              id={`loc-${index}`}
              className="input"
              value={level.selected}
              onChange={(e) => choose(index, e.target.value)}
            >
              <option value="">Select…</option>
              {level.options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name} ({o.kind})
                </option>
              ))}
            </select>
          </Field>
        ))}
      </div>
      {value == null && !error && levels.length > 0 && (
        <p className="field-hint mt-1">Keep choosing until no further options appear.</p>
      )}
      {error && (
        <p id="location-error" className="field-error" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}

/** Asset dropdown for the chosen location. "I don't know" is a valid, explicit choice. */
export function AssetPicker({ locationId, value, onChange, departmentId }) {
  const [assets, setAssets] = useState([]);
  useEffect(() => {
    let active = true;
    if (!locationId) {
      queueMicrotask(() => active && setAssets([]));
      return () => {
        active = false;
      };
    }
    api
      .get("/reference/assets", { params: { location_id: locationId } })
      .then(({ data }) => active && setAssets(data))
      .catch(() => active && setAssets([]));
    return () => {
      active = false;
    };
  }, [locationId]);
  const visible = departmentId
    ? assets.filter((a) => a.department_id === Number(departmentId))
    : assets;
  if (!locationId || visible.length === 0) return null;
  return (
    <Field
      label="Which item is affected?"
      htmlFor="asset"
      hint="Pick the exact item so your report joins the right ticket. Choose “I don’t know” if you are unsure."
    >
      <select
        id="asset"
        className="input"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">I don’t know</option>
        {visible.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name} ({a.tag})
          </option>
        ))}
      </select>
    </Field>
  );
}
