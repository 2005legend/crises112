# EIFS AI Service

FastAPI service providing STT, vision captioning, structured extraction, and semantic deduplication for the Emergency Intelligence Fusion System.

Runs on **port 8001**.

## Install dependencies

```bash
cd ai_service
pip install -r requirements.txt
```

## Environment variables

```bash
export GROQ_API_KEY=your_groq_api_key_here
```

The Groq API key is required for the `/extract` and `/ai/fuse-report` endpoints.
LLaVA vision requires [Ollama](https://ollama.ai) running locally with the `llava` model pulled:

```bash
ollama pull llava
```

## Run the service

```bash
cd ai_service
uvicorn main:app --host 0.0.0.0 --port 8001
```

Or with auto-reload for development:

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ai/health` | Model load status |
| POST | `/stt` | Audio → transcript |
| POST | `/vision` | Image → caption + entities |
| POST | `/extract` | Text → structured JSON |
| POST | `/dedup` | Summary + candidates → match decision |
| POST | `/dedup/batch-test` | Precision/recall evaluation |
| POST | `/ai/fuse-report` | Full pipeline in one call |

Interactive docs: `http://localhost:8001/docs`

## Run tests

```bash
cd ai_service
pytest tests/ -v
```

Skip slow latency tests in CI:

```bash
pytest tests/ -v -m "not slow"
```
