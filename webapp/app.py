# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import RootModel, BaseModel
from pathlib import Path
import json, uuid, datetime, uvicorn
from typing import Optional, Dict, Any


def run_semantic(page: dict):
    return [{"node": "#h3-12",
             "issue_type": "heading-order",
             "detail": "H3 appears before H2."}]

def run_contrast(page: dict):
    return [{"node": "#cta-btn",
             "issue_type": "color-contrast",
             "detail": "4.1:1 contrast"}]

def run_caption(page: dict):
    return [{"node": "img[alt='']",
             "issue_type": "image-alt-missing",
             "detail": "Missing alt"}]

def run_fixer(detectors: dict):
    fixes = []
    for d in detectors["contrast"]:
        fixes.append({**d,
                      "fix": "Darken text to #374151 for 7.2 : 1 contrast"})
    for d in detectors["caption"]:
        fixes.append({**d,
                      "fix": "Add alt='Company logo: stylised dragon'"})
    return fixes

app = FastAPI(title="Accessibility Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         
    allow_methods=["POST"],
    allow_headers=["*"],
)

class PageSnapshot(RootModel):
    root: dict                  

class Feedback(BaseModel):
    page_id: str
    suggestion: Dict[str, Any]
    action: str             
    comment: Optional[str] = None

@app.post("/analyze")
def analyze(snapshot: PageSnapshot):
    page = snapshot.root
    try:
        semantic = run_semantic(page)
        contrast = run_contrast(page)
        caption  = run_caption(page)
        fixer    = run_fixer({
            "semantic": semantic,
            "contrast": contrast,
            "caption" : caption
        })
        return {
            "semantic": semantic,
            "contrast": contrast,
            "caption" : caption,
            "fixer"   : fixer,
            "page_id" : page.get("page_id", str(uuid.uuid4()))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

FEEDBACK_STORE = Path("feedback_store.json")
FEEDBACK_STORE.write_text("[]") if not FEEDBACK_STORE.exists() else None

@app.post("/feedback")
def save_feedback(fb: Feedback):
    row = fb.dict()
    row["timestamp"] = datetime.datetime.utcnow().isoformat()
    data = json.loads(FEEDBACK_STORE.read_text())
    data.append(row)
    FEEDBACK_STORE.write_text(json.dumps(data, indent=2))
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,          # hot-reload for dev
        log_level="info"
    )
