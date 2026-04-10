/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useState, useEffect, useCallback } from 'react';
import { fetchIncidents } from '../services/api';

export const IncidentContext = createContext();

export const IncidentProvider = ({ children }) => {
  const [incidents, setIncidents] = useState([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);
  const [filters, setFilters] = useState({
    severity: 'All',
    status: 'All',
    timeRange: 'All'
  });
  const [isLoading, setIsLoading] = useState(true);

  const loadIncidents = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await fetchIncidents();
      setIncidents(data);
    } catch (error) {
      console.error("Failed to load incidents:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIncidents();
    // Simulate polling every 10 seconds for Phase 3
    const interval = setInterval(() => {
      loadIncidents();
    }, 10000);
    return () => clearInterval(interval);
  }, [loadIncidents]);

  const updateIncidentLocally = (id, newStatus) => {
    setIncidents(prev => prev.map(inc => inc.id === id ? { ...inc, status: newStatus } : inc));
  };

  const filteredIncidents = incidents.filter(inc => {
    if (filters.severity !== 'All' && inc.severity !== filters.severity) return false;
    if (filters.status !== 'All' && inc.status !== filters.status) return false;
    return true;
  });

  const selectedIncident = incidents.find(i => i.id === selectedIncidentId);

  return (
    <IncidentContext.Provider value={{
      incidents: filteredIncidents,
      allIncidents: incidents, // raw
      selectedIncident,
      selectedIncidentId,
      setSelectedIncidentId,
      filters,
      setFilters,
      isLoading,
      updateIncidentLocally
    }}>
      {children}
    </IncidentContext.Provider>
  );
};
