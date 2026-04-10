import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { IncidentProvider } from './contexts/IncidentContext';
import Dashboard from './pages/Dashboard';
import './App.css';
import './index.css';

// A simple navigation header
const Header = () => {
  return (
    <header className="navbar">
      <div className="logo">
        <span className="icon">🚨</span> Emergency Dashboard
      </div>
      <nav className="nav-links">
        <Link to="/" className="active">Live Ops</Link>
      </nav>
      <div className="status-indicator">
        <div className="pulsing-dot"></div>
        System Live
      </div>
    </header>
  );
};

function App() {
  return (
    <IncidentProvider>
      <BrowserRouter>
        <div className="app-container">
          <Header />
          <Routes>
            <Route path="/" element={<Dashboard />} />
          </Routes>
        </div>
      </BrowserRouter>
    </IncidentProvider>
  );
}

export default App;