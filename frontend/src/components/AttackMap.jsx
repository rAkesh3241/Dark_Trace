import React, { useCallback, useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const AttackMap = ({ attacks, backendUrl }) => {
  const [positions, setPositions] = useState([]);

  const load = useCallback(() => {
    fetch(`${backendUrl}/api/attack-ips`)
      .then((response) => response.json())
      .then((data) => setPositions(data))
      .catch(() => {});
  }, [backendUrl]);

  useEffect(() => {
    load();
  }, [attacks, load]);

  const riskColor = (score) => {
    if (score >= 90) return '#ff5470';
    if (score >= 70) return '#ffd166';
    if (score >= 40) return '#00d1ff';
    return '#22f58b';
  };

  return (
    <div className="map-container">
      <MapContainer center={[20, 0]} zoom={2} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />
        {positions.map((pos, idx) => (
          <CircleMarker
            key={`${pos.ip || 'ip'}-${idx}`}
            center={[pos.lat, pos.lng]}
            radius={Math.max(6, Math.min(pos.count * 2, 20))}
            pathOptions={{
              color: riskColor(pos.risk_score),
              fillColor: riskColor(pos.risk_score),
              fillOpacity: 0.7,
              weight: 2,
            }}
          >
            <Popup>
              <div style={{ fontFamily: 'monospace', minWidth: 160 }}>
                <strong style={{ color: riskColor(pos.risk_score) }}>{pos.ip}</strong><br />
                Location: {[pos.city, pos.country].filter(Boolean).join(', ') || 'Unknown'}<br />
                Events: {pos.count}<br />
                Risk: {pos.risk_score}
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
};

export default AttackMap;
