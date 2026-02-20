async function loadMetrics() {
    try {
        const res = await fetch("/metrics");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // populate the card scores if present
        const readinessEl = document.querySelector('.card.readiness .score');
        const skillEl = document.querySelector('.card.skill .score');
        const resumeEl = document.querySelector('.card.resume .score');
        const interviewEl = document.querySelector('.card.interview .score');

        if (readinessEl && data.readiness !== undefined) readinessEl.textContent = data.readiness + '%';
        if (skillEl && data.skill !== undefined) skillEl.textContent = data.skill + '%';
        if (resumeEl && data.resume !== undefined) resumeEl.textContent = data.resume + '%';
        if (interviewEl && data.interview !== undefined) interviewEl.textContent = data.interview + '%';

        // Ensure clicking anywhere on a card navigates to its link (helpful if other handlers prevented default)
        document.querySelectorAll('.card').forEach(card => {
            // If card is already an <a>, browser handles navigation. For safety, add click handler.
            const href = card.getAttribute('href') || card.querySelector('a')?.getAttribute('href');
            if (href) {
                card.style.cursor = 'pointer';
                card.addEventListener('click', (e) => {
                    // allow ctrl/cmd click, middle click to open in new tab
                    if (e.ctrlKey || e.metaKey || e.button === 1) return;
                    window.location = href;
                });
            }
        });

    } catch (err) {
        console.error('Failed to load metrics', err);
    }
}
window.onload = loadMetrics;
