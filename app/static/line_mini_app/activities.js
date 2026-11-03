(() => {
    const target = document.getElementById('week-summary');
    const retry = document.getElementById('week-retry');
    if (!target) return;
    async function load() {
        target.setAttribute('aria-busy', 'true');
        retry.hidden = true;
        try {
            const response = await fetch(target.dataset.url, {
                credentials: 'same-origin', headers: {'Accept': 'text/html'},
                signal: AbortSignal.timeout(45000)
            });
            if (!response.ok || response.redirected) throw new Error('Summary unavailable');
            const html = await response.text();
            const fragment = new DOMParser().parseFromString(html, 'text/html');
            const summary = fragment.querySelector('.home-week-ai-summary');
            if (!summary) throw new Error('Invalid summary');
            target.replaceChildren(summary);
            retry.hidden = !summary.querySelector('.home-week-ai-summary-error');
        } catch (_) {
            target.replaceChildren();
            const title = document.createElement('h2');
            title.textContent = 'สรุปกิจกรรมสัปดาห์นี้ที่ท่านต้องเข้าร่วม';
            const message = document.createElement('p');
            message.className = 'activity-muted';
            message.textContent = 'โหลดสรุปไม่สำเร็จ กรุณาลองอีกครั้ง';
            target.append(title, message);
            retry.hidden = false;
        } finally {
            target.setAttribute('aria-busy', 'false');
        }
    }
    retry.addEventListener('click', load);
    load();
})();
