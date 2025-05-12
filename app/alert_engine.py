import os
from datetime import datetime

ERROR_REPORT_DIR = "app/error_reports"
os.makedirs(ERROR_REPORT_DIR, exist_ok=True)

def generate_alert(alert_type: str, description: str):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{alert_type.replace(' ', '_')}_{timestamp}.txt"
    path = os.path.join(ERROR_REPORT_DIR, filename)
    with open(path, "w") as f:
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Alert Type: {alert_type}\n")
        f.write(f"Description: {description}\n")
