from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from typing import Any

import serial

SOIL_DRY_RAW = 1023
SOIL_WET_RAW = 300


def soil_percent(raw: int) -> float:
    """Convierte ADC 1023 (seco, 0 %) y 300 (húmedo, 100 %) a porcentaje."""
    percentage = (SOIL_DRY_RAW - raw) * 100 / (SOIL_DRY_RAW - SOIL_WET_RAW)
    return round(min(100.0, max(0.0, percentage)), 1)


def parse_measurement_line(line: str, reading: dict[str, Any]) -> None:
    """Actualiza el borrador con un campo del formato serial del microcontrolador."""
    text = line.strip()
    if match := re.search(r"Fecha:\s*(\d{4}-\d{2}-\d{2})\s+Hora:\s*(\d{2}:\d{2}:\d{2})", text):
        reading["measured_at"] = datetime.strptime(
            f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M:%S"
        )
    elif match := re.search(r"Temperatura BMP:\s*(-?\d+(?:\.\d+)?)\s*C", text, re.IGNORECASE):
        reading["temperature_bmp"] = float(match.group(1))
    elif match := re.search(r"Presion:\s*(-?\d+(?:\.\d+)?)\s*hPa", text, re.IGNORECASE):
        reading["pressure_hpa"] = float(match.group(1))
    elif match := re.search(r"Temperatura DHT:\s*(-?\d+(?:\.\d+)?)\s*C", text, re.IGNORECASE):
        reading["temperature_dht"] = float(match.group(1))
    elif match := re.search(r"Humedad del aire:\s*(-?\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE):
        reading["relative_humidity"] = float(match.group(1))
    elif match := re.search(r"Humedad suelo RAW:\s*(\d+)", text, re.IGNORECASE):
        reading["soil_raw"] = int(match.group(1))


def _save_if_complete(app, db, model, data: dict[str, Any], state: dict[str, Any], lock: threading.Lock) -> bool:
    required = {
        "temperature_bmp", "pressure_hpa", "temperature_dht",
        "relative_humidity", "soil_raw",
    }
    if not required.issubset(data):
        return False

    measured_at = data.get("measured_at", datetime.now())
    raw = data["soil_raw"]
    with app.app_context():
        try:
            db.session.add(model(
                measured_at=measured_at,
                temperature_bmp=data["temperature_bmp"],
                temperature_dht=data["temperature_dht"],
                relative_humidity=data["relative_humidity"],
                pressure_hpa=data["pressure_hpa"],
                soil_raw=raw,
                soil_moisture=soil_percent(raw),
            ))
            db.session.commit()
            with lock:
                state.update(last_reading_at=measured_at.isoformat(sep=" "), message="Lectura guardada correctamente")
            return True
        except Exception as exc:
            db.session.rollback()
            with lock:
                state["message"] = f"Error guardando lectura: {exc}"
            return False


def read_serial_forever(app, port: str, baud_rate: int, db, model, state, lock) -> None:
    """Lee bloques de mediciones y reintenta la conexión si el puerto se interrumpe."""
    current: dict[str, Any] = {}
    while True:
        try:
            with serial.Serial(port, baud_rate, timeout=1) as connection:
                with lock:
                    state.update(connected=True, port=port, message=f"Conectado a {port} ({baud_rate} baudios)")
                current = {}
                while True:
                    line = connection.readline().decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if "NUEVA LECTURA" in line.upper():
                        current = {}
                        continue
                    parse_measurement_line(line, current)
                    if "soil_raw" in current:
                        if _save_if_complete(app, db, model, current, state, lock):
                            current = {}
        except (serial.SerialException, OSError) as exc:
            with lock:
                state.update(connected=False, message=f"Puerto serial desconectado: {exc}")
            time.sleep(3)
        except Exception as exc:
            with lock:
                state.update(connected=False, message=f"Error del lector serial: {exc}")
            time.sleep(3)
