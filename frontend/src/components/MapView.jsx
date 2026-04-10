import React, { useContext, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { IncidentContext } from '../contexts/IncidentContext';

// Fix for default marker icons in Leaflet + bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// A component to auto-pan the map to the selected incident
const MapUpdater = ({ center }) => {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.setView(center, 14, { animate: true });
    }
  }, [center, map]);
  return null;
};

const MapView = () => {
  const { incidents, selectedIncident, setSelectedIncidentId } = useContext(IncidentContext);

  const defaultCenter = [13.0827, 80.2707]; // Chennai
  const center = selectedIncident ? [selectedIncident.location.lat, selectedIncident.location.lng] : defaultCenter;

  return (
    <div className="map-container">
      <MapContainer center={defaultCenter} zoom={13} scrollWheelZoom={true} style={{ height: '100%', width: '100%', borderRadius: '12px' }}>
        <TileLayer
          attribution='&copy; <a href="https://osm.org/copyright">OSM</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <MapUpdater center={selectedIncident ? center : null} />
        {incidents.map(inc => (
          <Marker 
            key={inc.id} 
            position={[inc.location.lat, inc.location.lng]}
            eventHandlers={{
              click: () => setSelectedIncidentId(inc.id)
            }}
          >
            <Popup>
              <strong>{inc.type}</strong><br />
              Severity: {inc.severity}<br />
              <div style={{ color: 'var(--text-secondary)' }}>{inc.reportCount} reports fused</div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
};

export default MapView;
