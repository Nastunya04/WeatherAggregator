from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from celery.result import AsyncResult
import re
from tasks import fetch_weather_summary
from influx_logger import log_event
from alert_engine import generate_alert

app = FastAPI()

class CityRequest(BaseModel):
    city: str

@app.post("/weather")
async def get_weather(request: CityRequest):
    city = request.city.strip()
    # Detect attempted fraud (SQLi, script injection, control chars)
    if re.search(r"(drop\s+table|;--|<script>|delete\s+from|insert\s+into)", city, re.IGNORECASE):
        generate_alert("Attempted Fraud", f"Suspicious string detected: {city}")
        raise HTTPException(status_code=400, detail="Suspicious input detected")

    if re.search(r"\b\d{10}\b|@|\d{3}-\d{3}-\d{4}", city):
        generate_alert("Potential Personal Data", f"City field contains sensitive content: {city}")
        raise HTTPException(status_code=400, detail="Input may contain personal data")

    # 2. Then validate city format
    if not city or not city.replace(" ", "").isalpha():
        generate_alert("Invalid Input", f"Invalid city name: {city}")
        raise HTTPException(status_code=400, detail="Invalid city name")
    log_event(city=city, source="api", status="received")
    task = fetch_weather_summary.delay(city)
    return {"message": "Weather task submitted", "task_id": task.id}

@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None
    }
