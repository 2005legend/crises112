import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { IncidentProvider } from './contexts/IncidentContext';
import Dashboard from './pages/Dashboard';
import './App.css';
import './index.css';

// A simple navigation header
const Header = () => {
  const location = useLocation();
  const isDemo = location.pathname === '/demo';

  return (
    <header className="navbar">
      <div className="logo">
        <span className="icon">🚨</span> Emergency Dashboard
      </div>
      <nav className="nav-links">
        <Link to="/" className={!isDemo ? 'active' : ''}>Live Ops</Link>
        <Link to="/demo" className={isDemo ? 'active' : ''}>Demo Mode</Link>
      </nav>
      <div className="status-indicator">
        <div className="pulsing-dot"></div>
        System Live
      </div>
    </header>
  );
};

import Demo from './pages/Demo';

function App() {
  return (
    <IncidentProvider>
      <BrowserRouter>
        <div className="app-container">
          <Header />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/demo" element={<Demo />} />
          </Routes>
        </div>
      </BrowserRouter>
    </IncidentProvider>
  );
}

export default App;