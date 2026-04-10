import React, { useContext } from 'react';
import { IncidentContext } from '../contexts/IncidentContext';

const MetricsPanel = () => {
  const { allIncidents } = useContext(IncidentContext);
  
  // Basic derived metrics
  const totalIncidents = allIncidents.length;
  const totalReports = allIncidents.reduce((sum, inc) => sum + (inc.reportCount || 0), 0);
  const duplicateReduction = totalReports > 0 ? Math.round(((totalReports - totalIncidents) / totalReports) * 100) : 0;
  
  return (
    <div className="metrics-panel">
      <div className="metric-card">
        <div className="metric-title">Live Incidents</div>
        <div className="metric-value">{totalIncidents}</div>
      </div>
      <div className="metric-card">
        <div className="metric-title">Raw Reports Fused</div>
        <div className="metric-value">{totalReports}</div>
      </div>
      <div className="metric-card">
        <div className="metric-title">Noise Reduction</div>
        <div className="metric-value">{duplicateReduction}%</div>
      </div>
      <div className="metric-card">
        <div className="metric-title">Avg Triage Time</div>
        <div className="metric-value">1.2m <span className="trend down">↓</span></div>
      </div>
    </div>
  );
};

export default MetricsPanel;
