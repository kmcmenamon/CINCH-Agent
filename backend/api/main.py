from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/query")
async def query(request: dict):
    try:
        data = await request.json() if hasattr(request, 'json') else request
        return {
            "answer": f"Test response to: {data.get('question', 'unknown')}. In production, this would query Claude with your uploaded codes.",
            "citations": ["Test citation"],
        }
    except:
        return {
            "answer": "Test response working!",
            "citations": [],
        }

@app.post("/standards/upload")
async def upload():
    return {"status": "success", "message": "PDF uploaded (test mode)"}

@app.get("/standards")
async def list_standards(customer_id: str):
    return [{"id": "1", "name": "Test Standard", "year": 2024}]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)