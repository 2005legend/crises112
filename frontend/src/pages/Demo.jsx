import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const DEMO_STEPS = [
  { id: 1, text: "Wait for system readiness...", delay: 2000, trigger: "auto" },
  { id: 2, text: "Voice Alert: 'Accident near Anna Nagar, 2 injured'", delay: 3000, trigger: "auto" },
  { id: 3, text: "NLP Extraction: Location=Anna Nagar, Modality=Voice, Injured=2", delay: 2000, trigger: "auto" },
  { id: 4, text: "Text Alert: 'Bike crash Anna Nagar signal'", delay: 2500, trigger: "auto" },
  { id: 5, text: "NLP Extraction: Encountered matching entity timeline. Fusing with [INC-9021].", delay: 3000, trigger: "auto" },
  { id: 6, text: "Image ingested: Analyzed damaged vehicle (Confidence: 94%)", delay: 2500, trigger: "auto" },
  { id: 7, text: "Deduplication complete. Severity scored as HIGH.", delay: 3000, trigger: "auto" }
];

const Demo = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!isPlaying) return;

    if (currentStep < DEMO_STEPS.length) {
      const step = DEMO_STEPS[currentStep];
      const timer = setTimeout(() => {
        setCurrentStep(prev => prev + 1);
      }, step.delay);
      return () => clearTimeout(timer);
    } else {
      // Scenario done, auto-redirect back to dashboard after a short pause
      const timer = setTimeout(() => {
        navigate('/');
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [isPlaying, currentStep, navigate]);

  return (
    <div className="demo-layout pane mx-auto mt-4" style={{ maxWidth: '600px' }}>
      <div className="text-center mb-4">
        <h2>Scenario Player</h2>
        <p className="text-muted">For presentation dry runs (Projector optimized)</p>
      </div>

      <div className="demo-controls flex-center mb-4">
        {!isPlaying ? (
          <button className="btn btn-primary btn-lg" onClick={() => setIsPlaying(true)}>
            ▶ Play "Downtown Emergency" Scenario
          </button>
        ) : (
          <div className="status-indicator" style={{ display: 'inline-flex' }}>
            <div className="pulsing-dot" style={{ backgroundColor: 'var(--color-warning)' }}></div>
            <span style={{ color: 'var(--color-warning)' }}>Scenario Running...</span>
          </div>
        )}
      </div>

      <div className="demo-timeline" style={{ background: 'var(--bg-base)', padding: '1rem', borderRadius: '8px' }}>
        {DEMO_STEPS.map((step, index) => (
          <div 
            key={step.id} 
            className="demo-step"
            style={{ 
              opacity: currentStep >= index ? 1 : 0.2,
              padding: '0.75rem',
              borderLeft: `2px solid ${currentStep > index ? 'var(--color-success)' : currentStep === index ? 'var(--accent-blue)' : 'var(--border-subtle)'}`,
              marginBottom: '0.5rem',
              transition: 'all 0.5s ease',
              transform: currentStep >= index ? 'translateX(0)' : 'translateX(-20px)'
            }}
          >
            {step.text}
            {currentStep > index && <span style={{ float: 'right', color: 'var(--color-success)' }}>✓</span>}
          </div>
        ))}

        {currentStep >= DEMO_STEPS.length && (
          <div className="text-center text-success mt-4">
            Scenario complete! Redirecting to live ops...
          </div>
        )}
      </div>
    </div>
  );
};

export default Demo;
