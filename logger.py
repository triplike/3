import csv
import os
from datetime import datetime
from typing import Dict


class DetectionLogger:
    def __init__(self, csv_path: str = "detections.csv"):
        self.csv_path = csv_path
        self._ensure_file()

    def _ensure_file(self):
        if os.path.exists(self.csv_path):
            return
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "color", "count", "details"])

    def log_counts(self, counts: Dict[str, int], details: str = ""):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for color, count in counts.items():
                if count > 0:
                    writer.writerow([ts, color, count, details])
