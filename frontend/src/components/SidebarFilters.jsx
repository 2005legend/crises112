import React, { useContext } from 'react';
import { IncidentContext } from '../contexts/IncidentContext';

const SidebarFilters = () => {
  const { filters, setFilters } = useContext(IncidentContext);

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="sidebar-filters">
      <h3 className="section-title">Filters</h3>

      <div className="filter-group">
        <label>Time Range</label>
        <div className="filter-chips">
          {['1h', '6h', '24h', 'All'].map(t => (
            <button 
              key={t}
              className={`chip ${filters.timeRange === t ? 'active' : ''}`}
              onClick={() => handleFilterChange('timeRange', t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <label>Severity</label>
        <div className="filter-chips">
          {['All', 'High', 'Medium', 'Low'].map(s => (
            <button 
              key={s}
              className={`chip severity-${s.toLowerCase()} ${filters.severity === s ? 'active' : ''}`}
              onClick={() => handleFilterChange('severity', s)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <label>Status</label>
        <div className="filter-chips">
          {['All', 'New', 'Acknowledged', 'Active', 'Resolved'].map(s => (
            <button 
              key={s}
              className={`chip ${filters.status === s ? 'active' : ''}`}
              onClick={() => handleFilterChange('status', s)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default SidebarFilters;
