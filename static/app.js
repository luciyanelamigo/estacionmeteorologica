const $ = (id) => document.getElementById(id);
let chart;
let lastReadingId = null;

const fmt = (value, digits = 1) => Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '—';
const dateFormatter = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'medium' });

function showToast(message) {
  const toast = $('toast');
  toast.textContent = message;
  toast.classList.add('visible');
  window.setTimeout(() => toast.classList.remove('visible'), 3200);
}

function updateStatus(status) {
  const connected = Boolean(status.connected);
  $('side-connection').textContent = connected ? `Serial conectado · ${status.port}` : status.message;
  $('side-pulse').classList.toggle('offline', !connected);
}

function updateCards(readings) {
  if (!readings.length) return;
  const latest = readings[readings.length - 1];
  $('temperature-bmp').textContent = fmt(latest.temperature_bmp, 1);
  $('temperature-dht').textContent = fmt(latest.temperature_dht, 1);
  $('relative-humidity').textContent = fmt(latest.relative_humidity, 1);
  $('pressure').textContent = fmt(latest.pressure_hpa, 1);
  $('soil-moisture').textContent = fmt(latest.soil_moisture, 0);
  $('soil-raw').textContent = latest.soil_raw;
  $('soil-progress').style.width = `${Math.max(0, Math.min(100, latest.soil_moisture))}%`;
  $('last-updated').textContent = `Última medición: ${dateFormatter.format(new Date(latest.measured_at))}`;
  if (lastReadingId !== null && latest.id > lastReadingId) showToast('Nueva medición recibida y guardada.');
  lastReadingId = latest.id;
}

function renderTable(readings) {
  const body = $('readings-body');
  $('record-count').textContent = `${readings.length} ${readings.length === 1 ? 'registro' : 'registros'}`;
  if (!readings.length) {
    body.innerHTML = '<tr><td class="loading-cell" colspan="7">Sin mediciones para mostrar. Verifique la conexión serial.</td></tr>';
    return;
  }
  body.innerHTML = readings.slice().reverse().map((row) => `<tr>
    <td class="date-cell">${dateFormatter.format(new Date(row.measured_at))}</td>
    <td>${fmt(row.temperature_bmp, 2)} <span class="unit">°C</span></td>
    <td>${fmt(row.temperature_dht, 2)} <span class="unit">°C</span></td>
    <td>${fmt(row.relative_humidity, 1)} <span class="unit">%</span></td>
    <td>${fmt(row.pressure_hpa, 2)} <span class="unit">hPa</span></td>
    <td><span class="soil-pill">${fmt(row.soil_moisture, 1)}%</span></td>
    <td>${row.soil_raw}</td>
  </tr>`).join('');
}

function renderChart(readings) {
  const canvas = $('history-chart');
  $('empty-chart').classList.toggle('visible', readings.length === 0);
  if (!readings.length) {
    if (chart) chart.destroy();
    chart = null;
    return;
  }
  const labels = readings.map((row) => dateFormatter.format(new Date(row.measured_at)));
  const options = {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Temperatura BMP (°C)', data: readings.map(r => r.temperature_bmp), borderColor: '#f5a65b', backgroundColor: '#f5a65b', yAxisID: 'yTemp', pointRadius: 0, borderWidth: 2, tension: .35 },
        { label: 'Temperatura DHT (°C)', data: readings.map(r => r.temperature_dht), borderColor: '#ee7183', backgroundColor: '#ee7183', yAxisID: 'yTemp', pointRadius: 0, borderWidth: 2, tension: .35 },
        { label: 'Humedad aire (%)', data: readings.map(r => r.relative_humidity), borderColor: '#61a9ff', backgroundColor: '#61a9ff', yAxisID: 'yPercent', pointRadius: 0, borderWidth: 2, tension: .35 },
        { label: 'Presión (hPa)', data: readings.map(r => r.pressure_hpa), borderColor: '#a68af7', backgroundColor: '#a68af7', yAxisID: 'yPressure', pointRadius: 0, borderWidth: 2, tension: .35 },
        { label: 'Humedad suelo (%)', data: readings.map(r => r.soil_moisture), borderColor: '#53c7a2', backgroundColor: '#53c7a2', yAxisID: 'yPercent', pointRadius: 0, borderWidth: 2, tension: .35 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#152435', padding: 12, titleFont: { family: 'DM Sans' }, bodyFont: { family: 'DM Sans' } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#758499', maxTicksLimit: 8, maxRotation: 0 }, border: { display: false } },
        yTemp: { position: 'left', title: { display: true, text: '°C', color: '#95a3b4' }, grid: { color: 'rgba(122,145,168,.10)' }, ticks: { color: '#758499' }, border: { display: false } },
        yPercent: { position: 'right', min: 0, max: 100, title: { display: true, text: '%', color: '#95a3b4' }, grid: { drawOnChartArea: false }, ticks: { color: '#758499' }, border: { display: false } },
        yPressure: { display: false, min: 850, max: 1100 },
      },
    },
  };
  if (chart) chart.destroy();
  chart = new Chart(canvas, options);
}

async function refresh() {
  try {
    const hours = $('range-select').value;
    const params = new URLSearchParams({ limit: '5000' });
    if (hours !== 'all') {
      const start = new Date(Date.now() - Number(hours) * 3600000);
      start.setMinutes(start.getMinutes() - start.getTimezoneOffset());
      params.set('start', start.toISOString().slice(0, 19));
    }
    const [readingsResponse, statusResponse] = await Promise.all([fetch(`/api/readings?${params}`), fetch('/api/status')]);
    if (!readingsResponse.ok || !statusResponse.ok) throw new Error('No se pudieron cargar los datos.');
    const readings = await readingsResponse.json();
    updateStatus(await statusResponse.json());
    updateCards(readings);
    renderTable(readings);
    renderChart(readings);
  } catch (error) {
    $('side-connection').textContent = 'No se pudo consultar el servidor';
    showToast(error.message || 'Error de conexión.');
  }
}

$('current-date').textContent = new Intl.DateTimeFormat('es', { dateStyle: 'full' }).format(new Date());
$('refresh-button').addEventListener('click', refresh);
$('range-select').addEventListener('change', refresh);
refresh();
window.setInterval(refresh, 15000);
