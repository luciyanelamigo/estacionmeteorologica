# Estación meteorológica local

Aplicación web para leer las mediciones del microcontrolador por puerto serial, almacenarlas en MySQL y consultar su historial en una tabla y un gráfico.

## Qué registra

- Temperatura BMP (°C) y temperatura DHT (°C).
- Humedad relativa del aire (%).
- Presión atmosférica (hPa).
- Humedad del suelo, valor RAW y porcentaje calculado.

La conversión del suelo respeta los extremos indicados: RAW `1023` = `0 %` (seco) y RAW `300` = `100 %` (húmedo). Entre ambos se usa interpolación lineal y se limita el resultado al intervalo 0–100 %.

## Requisitos

- Python 3.10 o superior.
- MySQL Server local iniciado.
- Acceso al puerto serial del Arduino/ESP.

## Preparar MySQL

Ejecute en MySQL con una cuenta administradora:

```sql
CREATE DATABASE estacion_meteorologica CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'weather'@'localhost' IDENTIFIED BY 'weather';
GRANT ALL PRIVILEGES ON estacion_meteorologica.* TO 'weather'@'localhost';
FLUSH PRIVILEGES;
```

Cambie la contraseña por una propia si lo desea y actualice `DATABASE_URL` en `.env`. La aplicación crea la tabla automáticamente al iniciar.

## Instalar y arrancar

1. Cree y active un entorno virtual Python.
2. Instale las dependencias de `requirements.txt`.
3. Copie `.env.example` como `.env`.
4. Configure `SERIAL_PORT` con el dispositivo correcto y `SERIAL_BAUD` con la velocidad configurada en el firmware. En Linux suele ser `/dev/ttyUSB0` o `/dev/ttyACM0`; el usuario que ejecuta la aplicación debe tener permiso de lectura/escritura del dispositivo (frecuentemente pertenece al grupo `dialout`).
5. Inicie la aplicación con `python app.py` y abra `http://localhost:5000`.

Por defecto se usa 9600 baudios. Si el serial monitor y la aplicación intentan abrir el mismo puerto simultáneamente, cierre el serial monitor: normalmente el puerto solo admite un lector a la vez.

## Formato serial esperado

El lector consume líneas UTF-8 organizadas así; el orden de los campos puede variar dentro de cada bloque:

```text
-- NUEVA LECTURA ---
Fecha: 2026-10-27 Hora: 13:59:17
Temperatura BMP: 22.46 C
Presion: 1020.04 hPa
Temperatura DHT: 21.20 C
Humedad del aire: 65.00 %
Humedad suelo RAW: 1022
```

El bloque se guarda cuando llega `Humedad suelo RAW` y están presentes todos los campos requeridos. Se aceptan fechas `YYYY-MM-DD` y horas `HH:MM:SS`. Si falta fecha/hora se utiliza el reloj local del servidor.

## API local

- `GET /api/readings?limit=500` lista las lecturas; `start` y `end` opcionales aceptan fechas ISO 8601.
- `GET /api/status` devuelve el estado del puerto serial y la cantidad total de registros.

La interfaz actualiza automáticamente cada 15 segundos. Chart.js y las fuentes tipográficas se cargan desde CDN, por lo que esas partes visuales requieren conexión a Internet; la aplicación y MySQL son locales.
