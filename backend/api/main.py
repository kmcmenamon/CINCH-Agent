from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo
projects = {}
standards = {}

@app.post("/standards/upload")
async def upload_standard(
    customer_id: str = Form(...),
    standard_name: str = Form(...),
    edition_year: int = Form(...),
    doc_type: str = Form("standard"),
    file: UploadFile = File(...),
):
    std_id = str(uuid.uuid4())
    standards[std_id] = {
        "id": std_id,
        "standard_name": standard_name,
        "edition_year": edition_year,
        "display_label": f"{standard_name} {edition_year}",
        "status": "ready",
        "total_chunks": 100,
        "total_pages": 50,
    }
    return {
        "standard_id": std_id,
        "status": "ready",
        "doc_type": doc_type,
        "message": f"Upload started for {standard_name} {edition_year}",
    }

@app.get("/standards")
async def list_standards(customer_id: str):
    return list(standards.values())

@app.get("/standards/{standard_id}/status")
async def get_standard_status(standard_id: str, customer_id: str):
    if standard_id in standards:
        return standards[standard_id]
    return JSONResponse(status_code=404, content={"error": "Not found"})

@app.post("/projects")
async def create_project(request: Request):
    try:
        data = await request.json()
        customer_id = data.get("customer_id")
        name = data.get("name")
        description = data.get("description", "")
        jurisdiction = data.get("jurisdiction", "")
        
        project_id = str(uuid.uuid4())
        projects[project_id] = {
            "id": project_id,
            "customer_id": customer_id,
            "name": name,
            "description": description,
            "jurisdiction": jurisdiction,
            "pinned_standards": [],
            "created_at": "2026-06-16",
        }
        return {
            "project_id": project_id,
            "name": name,
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.get("/projects")
async def list_projects(customer_id: str):
    result = [p for p in projects.values() if p.get("customer_id") == customer_id]
    return result

@app.post("/projects/{project_id}/standards")
async def pin_standard_to_project(project_id: str, request: Request):
    try:
        data = await request.json()
        uploaded_standard_id = data.get("uploaded_standard_id")
        
        if project_id not in projects:
            return JSONResponse(status_code=404, content={"error": "Project not found"})
        if uploaded_standard_id not in standards:
            return JSONResponse(status_code=404, content={"error": "Standard not found"})
        
        projects[project_id]["pinned_standards"].append({
            "standard_name": standards[uploaded_standard_id]["standard_name"],
            "edition_year": standards[uploaded_standard_id]["edition_year"],
            "display_label": standards[uploaded_standard_id]["display_label"],
        })
        
        return {
            "message": f"Pinned {standards[uploaded_standard_id]['standard_name']} to project",
            "project_id": project_id,
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.post("/query")
async def query_standards(request: Request):
    try:
        data = await request.json()
        return {
            "answer": "This is a test response from CINCH. In production, this would search your standards and return cited answers.",
            "citations": [],
            "standards_consulted": ["Your Standards"],
            "latency_ms": 100,
            "warning": "",
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

@app.post("/analyze")
async def analyze_design(request: Request):
    try:
        data = await request.json()
        return {
            "project_name": "Test Project",
            "standards_consulted": ["Your Standards"],
            "summary": "This is a test compliance analysis.",
            "pass_count": 5,
            "fail_count": 0,
            "review_count": 2,
            "items": [
                {
                    "requirement": "Test Requirement 1",
                    "status": "PASS",
                    "finding": "Design meets this requirement.",
                    "calculated_value": "Required: 100",
                    "design_value": "Provided: 150",
                    "citations": [],
                },
            ],
            "latency_ms": 200,
            "warning": "",
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
