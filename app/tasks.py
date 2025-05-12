from celery import Celery
import os
from influx_logger import log_event
from alert_engine import generate_alert

celery_app = Celery("weather_tasks")
celery_app.conf.broker_url = os.getenv("CELERY_BROKER_URL")
celery_app.conf.result_backend = os.getenv("CELERY_RESULT_BACKEND")

@celery_app.task(name="tasks.fetch_weather_summary")
def fetch_weather_summary(city: str):
    sources = {
        "source1": f"https://api.weatherapi1.com/data/{city}",
        "source2": f"https://api.weatherapi2.com/data/{city}",
        "source3": f"https://api.weatherapi3.com/data/{city}",
    }

    results = []
    errors = []

    for source_name, url in sources.items():
        try:
            data = {"temperature": 20 + hash(source_name + city) % 5}  # Simulated
            temperature = data["temperature"]
            log_event(city=city, source=source_name, status="success", description=f"{temperature}°C")
            results.append(temperature)
        except Exception as e:
            msg = f"Error fetching from {source_name} for city {city}: {str(e)}"
            log_event(city=city, source=source_name, status="fail", level="error", description=msg)
            generate_alert("API Failure", msg)
            errors.append(source_name)

    if not results:
        return {"error": "All sources failed for this city."}

    avg_temp = round(sum(results) / len(results), 2)
    return {
        "city": city,
        "avg_temperature": avg_temp,
        "sources_used": len(results),
        "sources_failed": errors
    }
