from fastapi import FastAPI
from routes import reports, incidents, metrics, websocket

app = FastAPI()

app.include_router(reports.router)
app.include_router(incidents.router)
app.include_router(metrics.router)
app.include_router(websocket.router)

@app.get("/health")
def health():
    return {"status": "ok"}
