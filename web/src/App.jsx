import React, { useEffect, useState } from "react";
import { CircleMarker, MapContainer, TileLayer } from "react-leaflet";

const mapCenter = [28.61, 77.21];
const riskUrl = import.meta.env.VITE_API_URL || "/mock-risk.json";
const fallbackDisclaimer = "Prototype. Estimated risk, not an official warning.";
const fallbackCredit = "Weather data by Open-Meteo.com";

const tierColors = {
  green: "#2e8b57",
  yellow: "#d39e00",
  orange: "#ef7d23",
  red: "#cf3c34",
  unknown: "#7b858b",
};

function formatLocalTime(value) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function getTier(tier) {
  return Object.hasOwn(tierColors, tier) ? tier : "unknown";
}

export default function App() {
  const [hotspots, setHotspots] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [selectedHotspot, setSelectedHotspot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [forecastUnavailable, setForecastUnavailable] = useState(false);
  const [locationError, setLocationError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadForecast() {
      try {
        const response = await fetch(riskUrl, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`Forecast request failed (${response.status}).`);
        }

        const data = await response.json();
        if (!Array.isArray(data.hotspots)) {
          throw new Error("The forecast response has an unexpected format.");
        }

        setForecast(data);
        setHotspots(data.hotspots);
      } catch (error) {
        if (controller.signal.aborted) return;

        // Keep locations visible in grey when the forecast service is unavailable.
        setForecastUnavailable(true);
        try {
          const response = await fetch(
            `${import.meta.env.BASE_URL}hotspots.json`,
            { signal: controller.signal },
          );
          if (!response.ok) {
            throw new Error(`Hotspot locations could not be loaded (${response.status}).`);
          }
          const data = await response.json();
          if (!Array.isArray(data.hotspots)) {
            throw new Error("The hotspots file has an unexpected format.");
          }
          setHotspots(data.hotspots);
        } catch (fallbackError) {
          if (!controller.signal.aborted) {
            setLocationError(fallbackError.message);
          }
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    loadForecast();
    return () => controller.abort();
  }, []);

  const disclaimer = forecast?.disclaimer ?? fallbackDisclaimer;
  const credit = forecast?.credit ?? fallbackCredit;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">
          U
        </div>
        <div>
          <p className="eyebrow">DELHI</p>
          <h1>Underpass Watch</h1>
        </div>
      </header>

      {forecast?.mock === true && (
        <div className="mock-banner" role="alert">
          MOCK DATA, NOT A REAL FORECAST
        </div>
      )}

      <section className="map-layout" aria-label="Delhi hotspot map">
        <aside className="info-panel">
          <p className="eyebrow">CITY MAP</p>
          <h2>Waterlogging hotspots</h2>
          <p className="panel-copy">
            Select a marker to view its forecast and evidence.
          </p>
          <div className="map-key">
            {Object.entries(tierColors).map(([tier, color]) => (
              <span className="key-item" key={tier}>
                <span
                  className="key-dot"
                  style={{ backgroundColor: color }}
                  aria-hidden="true"
                />
                {tier}
              </span>
            ))}
          </div>

          {loading && <p className="load-message">Loading forecast…</p>}
          {forecastUnavailable && (
            <p className="error-message" role="alert">
              Forecast unavailable
            </p>
          )}
          {locationError && (
            <p className="error-message" role="alert">
              {locationError}
            </p>
          )}

          {selectedHotspot && (
            <section className="hotspot-card" aria-live="polite">
              <div className="hotspot-details">
                <p className="eyebrow">SELECTED HOTSPOT</p>
                <h2>{selectedHotspot.name}</h2>
                {forecastUnavailable ? (
                  <p className="error-message">Forecast unavailable</p>
                ) : (
                  <>
                    <span
                      className={`tier-label tier-${getTier(selectedHotspot.tier)}`}
                    >
                      {getTier(selectedHotspot.tier)}
                    </span>
                    <dl className="forecast-details">
                      <dt>Forecast</dt>
                      <dd>
                        3-hour max: {selectedHotspot.forecast?.max_3h_mm ?? "—"} mm
                        <br />
                        1-hour max: {selectedHotspot.forecast?.max_1h_mm ?? "—"} mm
                      </dd>
                      <dt>Limit</dt>
                      <dd>{selectedHotspot.limit?.rain3h_mm ?? "—"} mm (3 h)</dd>
                      <dt>Risk window</dt>
                      <dd>
                        {selectedHotspot.forecast?.window_start &&
                        selectedHotspot.forecast?.window_end
                          ? `${formatLocalTime(selectedHotspot.forecast.window_start)} to ${formatLocalTime(selectedHotspot.forecast.window_end)}`
                          : "none expected"}
                      </dd>
                      <dt>Evidence</dt>
                      <dd>{selectedHotspot.evidence ?? "—"}</dd>
                    </dl>
                    <details className="why-details">
                      <summary>Why this alert?</summary>
                      <p>{selectedHotspot.why ?? "—"}</p>
                    </details>
                  </>
                )}
              </div>
              <button
                type="button"
                className="close-button"
                aria-label="Close hotspot details"
                onClick={() => setSelectedHotspot(null)}
              >
                ×
              </button>
            </section>
          )}
          <p className="disclaimer">{disclaimer}</p>
        </aside>

        <div className="map-wrap">
          <MapContainer
            center={mapCenter}
            zoom={11}
            scrollWheelZoom
            className="delhi-map"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {/* Use the supplied coordinates; unavailable forecasts use grey markers. */}
            {hotspots.map((hotspot) => {
              const tier = forecastUnavailable
                ? "unknown"
                : getTier(hotspot.tier);
              return (
                <CircleMarker
                  key={hotspot.id}
                  center={[hotspot.lat, hotspot.lon]}
                  radius={8}
                  pathOptions={{
                    color: "#ffffff",
                    weight: 2,
                    fillColor: tierColors[tier],
                    fillOpacity: 1,
                  }}
                  eventHandlers={{
                    click: () => setSelectedHotspot({ ...hotspot, tier }),
                  }}
                />
              );
            })}
          </MapContainer>
        </div>
      </section>

      <footer className="app-footer">{credit}</footer>
    </main>
  );
}
