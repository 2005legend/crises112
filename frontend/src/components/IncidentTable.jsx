import React, { useContext } from 'react';
import { IncidentContext } from '../contexts/IncidentContext';
import { formatDistanceToNow } from 'date-fns';

const IncidentTable = () => {
  const { incidents, isLoading, selectedIncidentId, setSelectedIncidentId } = useContext(IncidentContext);

  if (isLoading && incidents.length === 0) {
    return (
      <div className="incident-table skeleton">
        <div className="skeleton-row"></div>
        <div className="skeleton-row"></div>
        <div className="skeleton-row"></div>
      </div>
    );
  }

  return (
    <div className="incident-table-container">
      <table className="incident-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Type</th>
            <th>Location</th>
            <th>Severity</th>
            <th>Status</th>
            <th>Reports</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map(inc => (
            <tr
              key={inc.id}
              className={selectedIncidentId === inc.id ? 'selected' : ''}
              onClick={() => setSelectedIncidentId(inc.id)}
            >
              <td className="cell-id">{inc.id}</td>
              <td className="cell-type">{inc.type}</td>
              <td className="cell-location">{inc.location.address}</td>
              <td className="cell-severity">
                <span className={`badge severity-${inc.severity.toLowerCase()}`}>
                  {inc.severity}
                </span>
              </td>
              <td className="cell-status">
                <span className={`chip status-${inc.status.toLowerCase()}`}>
                  {inc.status}
                </span>
              </td>
              <td className="cell-reports">
                <div className="report-count" title={`${inc.reportCount} reports fused here`}>
                  {inc.reportCount}
                </div>
              </td>
              <td className="cell-updated">
                {formatDistanceToNow(new Date(inc.updatedAt), { addSuffix: true })}
              </td>
            </tr>
          ))}
          {incidents.length === 0 && (
            <tr>
              <td colSpan="7" className="empty-state">No incidents match the filters.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default IncidentTable;