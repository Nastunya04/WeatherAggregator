# Weather Summary Aggregator

A cloud-native FastAPI application that allows users to submit a city name and receive aggregated weather data. The app features asynchronous processing with Celery, centralized logging to InfluxDB, and alert reporting to text files on suspicious or invalid inputs.

## Project Structure

```
weather_aggregator/
├── app/
│   ├── main.py
│   ├── tasks.py
│   ├── worker.py
│   ├── influx_logger.py
│   ├── alert_engine.py
│   └── error_reports/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

## Features

- Submit a city name to get aggregated weather from 3 mocked sources.
- Logging of all actions to InfluxDB.
- Alert system generates `.txt` reports for:
  - Invalid input
  - Personal data leakage
  - Attempted fraud (e.g. SQL injection)
- Asynchronous background task processing with 2 Celery workers.
---

## Setup Instructions

### Prerequisites

- Docker & Docker Compose
- `.env` file with:

```env
INFLUX_URL=http://influxdb:8086
INFLUX_TOKEN=supersecrettoken
INFLUX_ORG=weather_org
INFLUX_BUCKET=weather_logs
INFLUX_USERNAME=admin
INFLUX_PASSWORD=adminpassword

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

### Run the System

```bash
docker-compose down --volumes  # Clean state
docker-compose up --build
```

---

## How to Use

### Submit a city:

```bash
curl -X POST http://localhost:8000/weather      -H "Content-Type: application/json"      -d '{"city": "Lviv"}'
```

Returns:

```json
{"message": "Weather task submitted", "task_id": "..."}
```

### Check task status:

```bash
curl http://localhost:8000/task/<task_id>
```
##### You should receive one of the following JSON responses depending on the task status:

- If the task is still running:
```json
{
  "task_id": "<task_id>",
  "status": "PENDING",
  "result": null
}
```
- If the task completed successfully:
```json
{
  "task_id": "<task_id>",
  "status": "SUCCESS",
  "result": {
    "city": "Lviv",
    "avg_temperature": 21.67,
    "sources_used": 3,
    "sources_failed": []
  }
}
```
- If the task failed or encountered an error:
```
{
  "task_id": "<task_id>",
  "status": "FAILURE",
  "result": "Exception details or None"
}
```
---
## Implementation Overview
### Logging to InfluxDB

- Implemented via `influx_logger.py`
- Stores: city, status, level, source, description

##### Check InfluxDB from Docker:
After starting the application with `docker-compose up --build`, you can verify that logs are successfully written to InfluxDB by running the following commands inside the InfluxDB container:

```bash
docker exec -it influxdb bash
```
```
export INFLUX_URL=http://influxdb:8086
export INFLUX_TOKEN=supersecrettoken
export INFLUX_ORG=weather_org
export INFLUX_BUCKET=weather_logs
export INFLUX_USERNAME=admin
export INFLUX_PASSWORD=adminpassword
```
```
influx query 'from(bucket: "weather_logs") |> range(start: -10m)' --org $INFLUX_ORG --token $INFLUX_TOKEN
```

### Alerts Engine

- Implemented in `alert_engine.py`
- Alerts for:
  - Invalid city (non-alpha)
  - Personal data (`@`, phone #)
  - Fraud attempt (e.g., `DROP TABLE`, `<script>`) 
- Creates `.txt` in `app/error_reports/`

##### Check Alert Engine:
After starting the application with `docker-compose up --build`, you can verify that the alert system is functioning correctly by sending invalid or suspicious inputs. Each alert will generate a `.txt` file in `app/error_reports/`.
- Example 1: Invalid City Name

```
curl -X POST http://localhost:8000/weather -H "Content-Type: application/json" -d '{"city": "!!!"}'
```
**Expected:** HTTP 400 response and a file like `Invalid_Input_...txt`

- Example 2: Personal Data (email address)
```
curl -X POST http://localhost:8000/weather -H "Content-Type: application/json" -d '{"city": "john@example.com"}'
```
**Expected:** HTTP 400 response and a file like `Potential_Personal_Data_...txt`

- Example 3: Attempted SQL Injection
```
curl -X POST http://localhost:8000/weather -H "Content-Type: application/json" -d '{"city": "Lviv; DROP TABLE users;--"}'
```
**Expected:** HTTP 400 response and a file like `Attempted_Fraud_...txt`

- **View the generated reports:**
```
ls app/error_reports/
```
- Example Alert Report (TXT):
```
Timestamp: 2025-05-11_21-12-05
Alert Type: Invalid Input
Description: Invalid city name: @@@
```
### Celery Workers

- 2 Celery workers defined in `docker-compose.yml`
- Background task: `fetch_weather_summary(city)`
- Uses `redis` as broker and result backend

##### Check Celery Execution:
After starting the application with `docker-compose up --build`, you can confirm that Celery workers are receiving and processing background tasks correctly.
- **Send a Task:**
```
curl -X POST http://localhost:8000/weather \
     -H "Content-Type: application/json" \
     -d '{"city": "Lviv"}'
```
- **View Logs for Celery Worker 1:**
```
docker logs celery_worker_1
```
- **View Logs for Celery Worker 2:**
```
docker logs celery_worker_2
```
- **Expected:** You should see logs like:
```
Task tasks.fetch_weather_summary[...] received
Task tasks.fetch_weather_summary[...] succeeded in ...s: {...}
```
---

## System Architecture

### System Components

| Component       | Role                                                                 |
|----------------|----------------------------------------------------------------------|
| `fastapi_app`   | Exposes the `/weather` API endpoint. Validates inputs, triggers Celery task, returns task ID. |
| `celery_worker_1` & `celery_worker_2` | Asynchronously handle `fetch_weather_summary(city)` tasks. Log results, simulate external API calls, raise alerts. |
| `redis`         | Acts as both the **Celery broker** and **result backend**. Enables async job dispatch and status tracking. |
| `influxdb`      | A time-series database that logs structured telemetry about every user request and API source interaction. |
| `alert_engine`  | Subsystem that writes alert `.txt` files to `app/error_reports/` when invalid input, personal data, or fraud is detected. |

### Operation Modes

| Operation                     | Type           | Handled by           |
|------------------------------|----------------|----------------------|
| Input validation             | Synchronous    | FastAPI              |
| Alert generation             | Synchronous    | FastAPI              |
| Logging to InfluxDB          | Sync           | Both FastAPI + Celery |
| Weather fetching + aggregation | Asynchronous  | Celery workers       |
| Status check via `/task/{id}`| Synchronous    | FastAPI + Redis      |

---

## Scaling Estimation

| Simultaneous Users | System Behavior & Load                                                                 | Recommended Scaling Strategy                                                                                                                                       |
|--------------------|------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **10 users**       | Light traffic, few requests per second. <10 concurrent background tasks.                | - 1 FastAPI container (handles sync input + response)<br>- 2 Celery workers (can handle tasks sequentially)<br>- Use default Redis & InfluxDB (no tuning needed)   |
| **50 users**       | Medium load: ~50 requests sent nearly simultaneously → 150 mock API calls via Celery.   | - Scale Celery workers to 3–4 for parallelism<br>- Add 1 more FastAPI instance behind load balancer (e.g. nginx)<br>- Increase Redis memory limit via config       |
| **100+ users**     | High load: 100+ concurrent requests, 300+ sub-tasks, frequent alerts/logs per second.   | - Deploy 3–5 FastAPI containers with Gunicorn/Uvicorn workers<br>- Run 6–8 Celery workers with concurrency flag<br>- Use managed Redis & InfluxDB for I/O handling |

---
