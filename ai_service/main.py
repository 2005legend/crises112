from fastapi import FastAPI
from contextlib import asynccontextmanager
from ai_service.engines.loader import ModelLoader
from ai_service.routers import stt, vision, extraction, dedup, fuse, health

model_loader = ModelLoader()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await model_loader.load_all()
    app.state.models = model_loader
    yield


app = FastAPI(
    title="EIFS AI Service",
    description="Speech-to-text, vision captioning, LLM extraction, and semantic deduplication for the Emergency Intelligence Fusion System.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router, tags=["Health"])
app.include_router(stt.router, prefix="/stt", tags=["STT"])
app.include_router(vision.router, prefix="/vision", tags=["Vision"])
app.include_router(extraction.router, prefix="/extract", tags=["Extraction"])
app.include_router(dedup.router, prefix="/dedup", tags=["Dedup"])
app.include_router(fuse.router, prefix="/ai", tags=["Fuse"])
