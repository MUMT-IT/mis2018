(() => {
    const card = document.querySelector('[data-quota-url]');
    if (!card) return;
    const content = document.getElementById('quota-content');
    const period = document.getElementById('quota-period');
    const retry = document.getElementById('quota-retry');
    function node(tag, className, text) {
        const element = document.createElement(tag);
        element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }
    function dateLabel(value) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error('Invalid date');
        return new Date(value + 'T00:00:00+07:00').toLocaleDateString('th-TH', {
            timeZone: 'Asia/Bangkok', day: 'numeric', month: 'short', year: 'numeric'
        });
    }
    async function load() {
        content.setAttribute('aria-busy', 'true');
        retry.hidden = true;
        try {
            const response = await fetch(card.dataset.quotaUrl, {
                credentials: 'same-origin', signal: AbortSignal.timeout(20000)
            });
            if (!response.ok || response.redirected) throw new Error('Quota unavailable');
            const quota = await response.json();
            const limit = Number(quota.quota_limit);
            const used = Number(quota.quota_used);
            const remaining = Number(quota.quota_remaining);
            if (![limit, used, remaining].every(Number.isFinite) || limit <= 0 || used < 0 || remaining < 0) {
                throw new Error('Invalid quota');
            }
            period.textContent = 'รอบโควตา ' + dateLabel(quota.quota_start) + ' – ' + dateLabel(quota.quota_end);
            const visual = node('div', 'quota-visual');
            const ring = node('div', 'quota-ring');
            ring.style.setProperty('--quota-progress', Math.min(100, used / limit * 100) + '%');
            ring.setAttribute('role', 'img');
            ring.setAttribute('aria-label', 'ใช้โควตาแล้ว ' + used + ' จาก ' + limit + ' วัน คงเหลือ ' + remaining + ' วัน');
            const center = node('div', 'quota-center');
            center.setAttribute('aria-hidden', 'true');
            center.append(node('strong', '', String(used)), node('span', '', 'จาก ' + limit + ' วัน'));
            ring.append(center);
            const stats = node('div', 'quota-stats');
            const available = node('p', 'quota-remaining');
            available.append(node('span', '', 'คงเหลือ '), node('strong', '', String(remaining)), node('span', '', ' วัน'));
            stats.append(available, node('p', '', 'ใช้แล้ว ' + used + ' วัน'), node('p', 'quota-note', 'ทั้งหมด ' + limit + ' วันต่อรอบ'));
            visual.append(ring, stats);
            content.replaceChildren(visual, node('p', 'quota-note', 'นับวันที่เข้างานสายและ/หรือชั่วโมงทำงานไม่ครบ ตามเกณฑ์ MIS โดยนับเป็นวัน ไม่ใช่จำนวนคำขอรับรองเวลา'));
        } catch (_) {
            period.textContent = 'ไม่สามารถโหลดข้อมูลโควตาได้';
            content.replaceChildren(node('p', 'quota-note', 'กรุณาลองอีกครั้ง รายการคำขอยังคงดูได้ตามปกติ'));
            retry.hidden = false;
        } finally {
            content.setAttribute('aria-busy', 'false');
        }
    }
    retry.addEventListener('click', load);
    load();
})();
