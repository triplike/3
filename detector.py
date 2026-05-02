import cv2
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class ColorRange:
    name: str
    lower: Tuple[int, int, int]
    upper: Tuple[int, int, int]
    box_color: Tuple[int, int, int]


class ColorDetector:
    def __init__(self, min_area: int = 800):
        self.min_area = min_area
        self.kernel = np.ones((5, 5), np.uint8)

    def _clean_mask(self, mask: np.ndarray) -> np.ndarray:
        mask = cv2.erode(mask, self.kernel, iterations=1)
        mask = cv2.dilate(mask, self.kernel, iterations=2)
        return mask

    def detect(
        self, frame: np.ndarray, color_ranges: List[ColorRange]
    ) -> Tuple[np.ndarray, Dict[str, int], List[Dict[str, str]]]:
        output = frame.copy()
        counts: Dict[str, int] = {item.name: 0 for item in color_ranges}
        events: List[Dict[str, str]] = []

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        for item in color_ranges:
            mask = cv2.inRange(hsv, np.array(item.lower), np.array(item.upper))
            mask = self._clean_mask(mask)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.min_area:
                    continue

                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(output, (x, y), (x + w, y + h), item.box_color, 2)
                label = f"{item.name} ({int(area)})"
                cv2.putText(output, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, item.box_color, 2)
                counts[item.name] += 1
                events.append({"color": item.name, "area": str(int(area))})

        return output, counts, events
