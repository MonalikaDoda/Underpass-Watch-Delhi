import React, { useEffect, useState } from "react";
import { CircleMarker, MapContainer, TileLayer } from "react-leaflet";

const mapCenter = [28.61, 77.21];

export default function App() {
  const [hotspots, setHotspots] = useState([]);
  const [selectedHotspot, setSelectedHotspot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    // Read the copied source data from Vite's public folder.
    fetch(`${import.meta.env.BASE_URL}hotspots.json`, {
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Hotspots could not be loaded (${response.status}).`);
        }
        return response.json();
      })
      .then((data) => {
        if (!Array.isArray(data.hotspots)) {
          throw new Error("The hotspots file has an unexpected format.");
        }
        setHotspots(data.hotspots);
        setLoading(false);
      })
      .catch((loadError) => {
        if (loadError.name !== "AbortError") {
          setError(loadError.message);
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

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

      <section className="map-layout" aria-label="Delhi hotspot map">
        <aside className="info-panel">
          <p className="eyebrow">CITY MAP</p>
          <h2>Waterlogging hotspots</h2>
          <p className="panel-copy">
            Select a marker to view the hotspot name.
          </p>
          <div className="map-key">
            <span className="key-dot" aria-hidden="true" />
            <span>Hotspot</span>
          </div>
          {loading && <p className="load-message">Loading hotspots…</p>}
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <p className="coordinate-note">
            Hotspot coordinates are approximate.
          </p>
          {selectedHotspot && (
            <section className="hotspot-card" aria-live="polite">
              <div>
                <p className="eyebrow">SELECTED HOTSPOT</p>
                <h2>{selectedHotspot.name}</h2>
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
            {/* Use the supplied approximate coordinates for each hotspot. */}
            {hotspots.map((hotspot) => (
              <CircleMarker
                key={hotspot.id}
                center={[hotspot.lat, hotspot.lon]}
                radius={8}
                pathOptions={{
                  color: "#ffffff",
                  weight: 2,
                  fillColor: "#7b858b",
                  fillOpacity: 1,
                }}
                eventHandlers={{
                  click: () => setSelectedHotspot(hotspot),
                }}
              />
            ))}
          </MapContainer>
        </div>
      </section>
    </main>
  );
}
