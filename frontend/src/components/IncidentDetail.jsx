import React, { useContext, useState } from 'react';
import { IncidentContext } from '../contexts/IncidentContext';
import { formatDistanceToNow } from 'date-fns';
import { Phone, MessageSquare, Image as ImageIcon, MapPin, AlertCircle, CheckCircle, Code } from 'lucide-react';
import { updateIncidentStatus } from '../services/api';
import AIViewer from './AIViewer';

const ModalityIcon = ({ modality }) => {
  switch (modality) {
    case 'phone': return <Phone size={16} className="text-blue" />;
    case 'sms': return <MessageSquare size={16} className="text-green" />;
    case 'image': return <ImageIcon size={16} className="text-purple" />;
    default: return <AlertCircle size={16} />;
  }
};

const IncidentDetail = () => {
  const { selectedIncident, updateIncidentLocally } = useContext(IncidentContext);
  const [isUpdating, setIsUpdating] = useState(false);


  if (!selectedIncident) {
    return (
      <div className="incident-detail empty flex-center">
        <div className="text-center">
          <AlertCircle size={48} className="text-muted mb-4 mx-auto" />
          <p>Select an incident from the table or map to view details.</p>
        </div>
      </div>
    );
  }

  const handleAction = async (newStatus) => {
    setIsUpdating(true);
    try {
      await updateIncidentStatus(selectedIncident.id, newStatus);
      updateIncidentLocally(selectedIncident.id, newStatus);
    } catch (e) {
      console.error(e);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="incident-detail">
      <header className="detail-header">
        <div className="flex-between">
          <h2>{selectedIncident.id}</h2>
          <span className={`badge severity-${selectedIncident.severity.toLowerCase()}`}>
            {selectedIncident.severity}
          </span>
        </div>
        <div className="text-muted flex-align-center gap-2 mt-2">
          <MapPin size={14} /> {selectedIncident.location.address}
        </div>
        <div className="text-muted flex-align-center gap-2 mt-1">
          <span className={`chip status-${selectedIncident.status.toLowerCase()}`}>
            {selectedIncident.status}
          </span>
          <span>•</span>
          <span>Updated {formatDistanceToNow(new Date(selectedIncident.updatedAt))} ago</span>
        </div>
      </header>

      <section className="detail-section">
        <h3>Description</h3>
        <p>{selectedIncident.description}</p>
      </section>

      {/* NEW: AI Data Viewer */}
      <section className="detail-section">
        <AIViewer data={selectedIncident.aiData} />
      </section>

      <section className="detail-section flex-1">
        <h3>Fused Reports ({selectedIncident.fusedReports?.length || 0})</h3>
        <div className="reports-list">
          {selectedIncident.fusedReports?.map(report => (
            <div key={report.id} className="report-card">
              <div className="report-header">
                <ModalityIcon modality={report.modality} />
                <span className="text-xs text-muted">
                  {formatDistanceToNow(new Date(report.timestamp))} ago
                </span>
              </div>
              <p className="report-text">{report.text}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="detail-footer">
        <button
          className="btn btn-primary w-100 mb-2"
          disabled={isUpdating || selectedIncident.status === 'Resolved'}
          onClick={() => handleAction('Acknowledged')}
        >
          {isUpdating ? 'Updating...' : 'Acknowledge Incident'}
        </button>
        <button
          className="btn btn-success w-100 flex-align-center justify-center gap-2"
          disabled={isUpdating || selectedIncident.status === 'Resolved'}
          onClick={() => handleAction('Resolved')}
        >
          <CheckCircle size={16} /> Mark Resolved
        </button>
      </footer>
    </div>
  );
};

export default IncidentDetail;
