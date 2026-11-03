from __future__ import annotations

import os
import threading
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc

load_dotenv()
db = SQLAlchemy()


class Reading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    measured_at = db.Column(db.DateTime, nullable=False, index=True)
    temperature_bmp = db.Column(db.Float, nullable=False)
    temperature_dht = db.Column(db.Float, nullable=False)
    relative_humidity = db.Column(db.Float, nullable=False)
    pressure_hpa = db.Column(db.Float, nullable=False)
    soil_raw = db.Column(db.Integer, nullable=False)
    soil_moisture = db.Column(db.Float, nullable=False)


_reader_lock = threading.Lock()
_reader_started = False
_reader_state = {
    "connected": False,
    "port": os.getenv("SERIAL_PORT", ""),
    "message": "Lector serial aún no iniciado",
    "last_reading_at": None,
}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://weather:weather@127.0.0.1:3306/estacion_meteorologica?charset=utf8mb4",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/readings")
    def readings():
        try:
            limit = min(max(int(request.args.get("limit", "500")), 1), 5000)
        except ValueError:
            return jsonify({"error": "El límite debe ser un número entero."}), 400

        query = Reading.query
        start = request.args.get("start")
        end = request.args.get("end")
        try:
            if start:
                query = query.filter(Reading.measured_at >= datetime.fromisoformat(start))
            if end:
                query = query.filter(Reading.measured_at <= datetime.fromisoformat(end))
        except ValueError:
            return jsonify({"error": "Fecha inválida; use el formato ISO 8601."}), 400

        rows = query.order_by(desc(Reading.measured_at)).limit(limit).all()
        rows.reverse()
        return jsonify([
            {
                "id": row.id,
                "measured_at": row.measured_at.isoformat(timespec="seconds"),
                "temperature_bmp": row.temperature_bmp,
                "temperature_dht": row.temperature_dht,
                "relative_humidity": row.relative_humidity,
                "pressure_hpa": row.pressure_hpa,
                "soil_raw": row.soil_raw,
                "soil_moisture": row.soil_moisture,
            }
            for row in rows
        ])

    @app.get("/api/status")
    def status():
        with _reader_lock:
            current = dict(_reader_state)
        try:
            current["total_readings"] = db.session.query(Reading.id).count()
            current["database"] = "conectada"
        except Exception as exc:
            db.session.rollback()
            current["database"] = f"error: {exc}"
        return jsonify(current)

    return app


def start_serial_reader(app: Flask) -> None:
    """Arranca un único hilo serial para evitar lectores duplicados en desarrollo."""
    global _reader_started
    port = os.getenv("SERIAL_PORT", "").strip()
    baud_rate = int(os.getenv("SERIAL_BAUD", "9600"))
    if not port:
        with _reader_lock:
            _reader_state.update(connected=False, message="Configure SERIAL_PORT en el archivo .env")
        return

    with _reader_lock:
        if _reader_started:
            return
        _reader_started = True
        _reader_state.update(port=port, message="Conectando al puerto serial…")

    from serial_reader import read_serial_forever

    threading.Thread(
        target=read_serial_forever,
        args=(app, port, baud_rate, db, Reading, _reader_state, _reader_lock),
        name="serial-reader",
        daemon=True,
    ).start()


app = create_app()

if __name__ == "__main__":
    # El proceso padre del reloader no debe abrir el puerto serial.
    if os.getenv("FLASK_DEBUG") != "1" or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_serial_reader(app)
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
