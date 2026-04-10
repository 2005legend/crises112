# integrations/ai_service.py

import requests
import json

AI_URL = "http://localhost:8001/ai/fuse-report"


def call_ai_service(payload: dict, candidates: list) -> dict:

    try:
        # Prepare base data
        data = {
            "modality": payload.get("source", "text"),
            "candidates_json": json.dumps(candidates)
        }

        files = None

        # HANDLE FILE INPUT (image / voice)
        if payload.get("source") in ["image", "voice"]:

            file_obj = payload.get("file")
            filename = payload.get("filename") or "upload.bin"

            if file_obj:
                files = {
                    "file": (
                        filename,
                        file_obj,
                        "application/octet-stream"
                    )
                }
            else:
                # fallback if file missing
                data["text"] = payload.get("text", "")

        # HANDLE TEXT INPUT
        else:
            data["text"] = payload.get("text", "")

        # MAKE REQUEST
        response = requests.post(
            AI_URL,
            data=data,
            files=files,
            timeout=10
        )

        # HANDLE BAD STATUS
        if response.status_code != 200:
            raise Exception(f"AI returned status {response.status_code}: {response.text}")

        # SAFE JSON PARSE
        try:
            result = response.json()
        except Exception:
            raise Exception("Invalid JSON response from AI")

        # STRICT VALIDATION
        if not isinstance(result, dict):
            raise Exception("AI response is not a dict")

        if "extracted" not in result:
            raise Exception("Missing 'extracted' field")

        # DEFAULT FIELDS
        result.setdefault("match", None)
        result.setdefault("similarity_score", 0)
        result.setdefault("merge_reason", "")
        result.setdefault("errors", None)

        return result

    except requests.exceptions.Timeout:
        print("AI SERVICE TIMEOUT")

    except requests.exceptions.ConnectionError:
        print("AI SERVICE NOT REACHABLE")

    except Exception as e:
        print("AI SERVICE FAILURE:", str(e))

    # FINAL SAFE FALLBACK (never break pipeline)
    return {
        "extracted": {
            "location_text": "unknown",
            "incident_type": "unknown",
            "affected": 0
        },
        "match": None,
        "similarity_score": 0,
        "merge_reason": "",
        "errors": "AI service failure"
    }