// src/services/api.js

export async function fetchIncidents() {
  try {
    // The vite.config.js proxy will route this to http://localhost:8000/api/incidents
    const response = await fetch('/api/incidents');
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
  } catch (error) {
    console.error("Error fetching incidents:", error);
    return [];
  }
}

export async function fetchIncidentDetails(id) {
  try {
    const response = await fetch(`/api/incidents/${id}`);
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
  } catch (error) {
    console.error(`Error fetching incident ${id}:`, error);
    return null;
  }
}

export async function updateIncidentStatus(id, newStatus) {
  try {
    const response = await fetch(`/api/incidents/${id}/status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ newStatus })
    });
    if (!response.ok) throw new Error('Network response was not ok');
    return await response.json();
  } catch (error) {
    console.error(`Error updating status for ${id}:`, error);
    throw error;
  }
}
