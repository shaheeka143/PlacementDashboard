async function loadMetrics() {
    const res = await fetch("/metrics");
    const data = await res.json();
    console.log(data);
}
window.onload = loadMetrics;
