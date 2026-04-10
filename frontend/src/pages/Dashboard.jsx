import React from 'react';
import SidebarFilters from '../components/SidebarFilters';
import IncidentTable from '../components/IncidentTable';
import MapView from '../components/MapView';
import IncidentDetail from '../components/IncidentDetail';
import MetricsPanel from '../components/MetricsPanel';

const Dashboard = () => {
  return (
    <div className="main-layout">
      {/* Left Sidebar: Filters */}
      <aside className="sidebar pane">
        <SidebarFilters />
      </aside>

      {/* Center: Table & Map */}
      <main className="content-area">
        <MetricsPanel />
        <section className="table-section pane">
          <IncidentTable />
        </section>
        
        <section className="map-section pane">
          <MapView />
        </section>
      </main>

      {/* Right Sidebar: Detail View */}
      <aside className="detail-panel pane">
        <IncidentDetail />
      </aside>
    </div>
  );
};

export default Dashboard;