import express from 'express';
import cors from 'cors';

const app = express();
const PORT = 8000;

app.use(cors());
app.use(express.json());

// In-memory Database of Incidents (The exact data we used on the frontend)
let databaseIncidents = [
  {
    id: "INC-9021",
    type: "Road Accident",
    location: { lat: 13.0850, lng: 80.2101, address: "Anna Nagar Signal, Chennai" },
    severity: "High",
    status: "Active",
    reportCount: 3,
    updatedAt: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
    description: "Multi-vehicle road accident near Anna Nagar signal. At least 2 confirmed injured.",
    fusedReports: [
      { id: "R-1", modality: "phone", text: "Accident near Anna Nagar, 2 injured.", timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString() },
      { id: "R-2", modality: "sms", text: "Bike crash Anna Nagar signal", timestamp: new Date(Date.now() - 1000 * 60 * 4).toISOString() },
      { id: "R-3", modality: "image", text: "[Image attached: Damaged Vehicle]", timestamp: new Date(Date.now() - 1000 * 60 * 2).toISOString() }
    ],
    aiData: {
      confidence: 0.94,
      model: "Llama-3-Emergency-Finelined v2",
      entities: ["vehicle", "injury (2)", "crossroad"],
      sentiment: "panic, urgent",
      source_modalities: ["voice", "text", "vision"],
      deduplication_score: 98.5
    }
  },
  {
    id: "INC-9022",
    type: "Fire",
    location: { lat: 13.0604, lng: 80.2496, address: "Mount Road, Chennai" },
    severity: "Medium",
    status: "Acknowledged",
    reportCount: 5,
    updatedAt: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
    description: "Minor electrical fire at a roadside transformer.",
    fusedReports: [
      { id: "R-4", modality: "phone", text: "Sparks coming from the transformer here.", timestamp: new Date(Date.now() - 1000 * 60 * 16).toISOString() },
      { id: "R-5", modality: "phone", text: "Transformer caught fire on Mount road.", timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString() }
    ],
    aiData: {
      confidence: 0.88,
      model: "Llama-3-Emergency-Finelined v2",
      entities: ["transformer", "electrical spark"],
      sentiment: "concerned",
      source_modalities: ["voice"],
      deduplication_score: 91.2
    }
  },
  {
    id: "INC-9023",
    type: "Hazard",
    location: { lat: 13.0012, lng: 80.2565, address: "Adyar, Chennai" },
    severity: "Low",
    status: "Resolved",
    reportCount: 1,
    updatedAt: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    description: "Tree branch fallen on the pedestrian path.",
    fusedReports: [
      { id: "R-6", modality: "sms", text: "Large tree branch blocking the walkway.", timestamp: new Date(Date.now() - 1000 * 60 * 130).toISOString() }
    ],
    aiData: {
      confidence: 0.99,
      model: "Llama-3-Emergency-Finelined v2",
      entities: ["tree", "obstruction"],
      sentiment: "neutral",
      source_modalities: ["text"],
      deduplication_score: 0
    }
  },
  {
    id: "INC-9024",
    type: "Medical",
    location: { lat: 12.9716, lng: 80.2428, address: "Taramani, Chennai" },
    severity: "High",
    status: "New",
    reportCount: 2,
    updatedAt: new Date(Date.now() - 1000 * 60 * 1).toISOString(),
    description: "Worker collapsed at construction site. Unresponsive.",
    fusedReports: [
      { id: "R-7", modality: "phone", text: "Man collapsed, please send ambulance fast!", timestamp: new Date(Date.now() - 1000 * 60 * 2).toISOString() },
      { id: "R-8", modality: "phone", text: "Need medic at site A, worker fainted.", timestamp: new Date(Date.now() - 1000 * 60 * 1).toISOString() }
    ],
    aiData: {
      confidence: 0.97,
      model: "Llama-3-Emergency-Finelined v2",
      entities: ["medical emergency", "unconscious", "construction"],
      sentiment: "highly urgent, panic",
      source_modalities: ["voice", "voice"],
      deduplication_score: 95.8
    }
  }
];

// GET: Fetch all active incidents
app.get('/api/incidents', (req, res) => {
  console.log(`[API] Fetching ${databaseIncidents.length} incidents...`);
  res.json(databaseIncidents);
});

// GET: Fetch single incident details
app.get('/api/incidents/:id', (req, res) => {
  const incident = databaseIncidents.find(i => i.id === req.params.id);
  if (incident) {
    res.json(incident);
  } else {
    res.status(404).json({ error: "Incident not found" });
  }
});

// POST: Update an incident's status
app.post('/api/incidents/:id/status', (req, res) => {
  const { newStatus } = req.body;
  
  if (!newStatus) {
    return res.status(400).json({ error: "No status provided in body" });
  }

  const incidentIndex = databaseIncidents.findIndex(i => i.id === req.params.id);
  
  if (incidentIndex > -1) {
    databaseIncidents[incidentIndex].status = newStatus;
    // Update its modified timestamp
    databaseIncidents[incidentIndex].updatedAt = new Date().toISOString();
    
    console.log(`[API] Updated ${req.params.id} -> ${newStatus}`);
    res.json({ success: true, updatedObject: databaseIncidents[incidentIndex] });
  } else {
    res.status(404).json({ error: "Incident not found" });
  }
});

app.listen(PORT, () => {
  console.log(`🚀 AI Backend running successfully on http://localhost:${PORT}`);
  console.log(`Available API Endpoints:`);
  console.log(`  -> GET  /api/incidents`);
  console.log(`  -> GET  /api/incidents/:id`);
  console.log(`  -> POST /api/incidents/:id/status`);
});
