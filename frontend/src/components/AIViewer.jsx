import React, { useState } from "react";

function AIViewer({ data }) {
  const [show, setShow] = useState(false);

  // If no data is provided, don't render the component
  if (!data) return null;

  return (
    <div className="ai-viewer-container" style={{ marginBottom: '1.5rem' }}>
      <button 
        onClick={() => setShow(!show)}
        className="btn"
        style={{ 
          width: '100%', 
          background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.1), rgba(14, 165, 233, 0.2))', 
          color: 'var(--accent-blue)', 
          border: '1px solid var(--border-focus)',
          boxShadow: '0 0 10px rgba(14, 165, 233, 0.15)',
          justifyContent: 'center',
          fontFamily: 'monospace'
        }}
      >
        🤖 {show ? 'Hide AI Extraction Data' : 'View AI Extraction Data'}
      </button>

      {show && (
        <div
          style={{
            background: "rgba(18, 27, 43, 0.8)",
            color: "var(--accent-blue)",
            padding: "15px",
            marginTop: "10px",
            fontFamily: "monospace",
            borderRadius: "8px",
            maxHeight: "250px",
            overflowY: "auto",
            border: "1px solid var(--border-focus)",
            boxShadow: "0 0 10px rgba(14, 165, 233, 0.1)",
            fontSize: "0.80rem"
          }}
        >
          <pre style={{ margin: 0 }}>{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default AIViewer;
