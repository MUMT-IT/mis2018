(() => {
    const config = document.currentScript.dataset;
    const dialog = document.getElementById('checkin-confirm');
    const status = document.getElementById('gps-status');
    const submit = document.getElementById('gps-submit');
    const retry = document.getElementById('gps-retry');
    const close = document.getElementById('gps-close');
    const browser = document.getElementById('gps-browser');
    const locations = [...document.querySelectorAll('.location')];
    const saveStatus = document.getElementById('save-status');
    let place = null;
    const maxDistance = Number(config.maxDistance);
    function distanceTo(lat, lon) {
        const rad = value => value * Math.PI / 180;
        const a = Math.sin(rad(lat - coordinates.lat) / 2) ** 2 +
            Math.cos(rad(coordinates.lat)) * Math.cos(rad(lat)) * Math.sin(rad(lon - coordinates.lon) / 2) ** 2;
        return 2 * 6571 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, a))));
    }
    const warning = document.getElementById('checkout-warning');
    let coordinates = null, acquiredAt = 0, busy = false, locating = false, confirmCheckout = false, saved = false;
    function update() {
        locations.forEach(button => {
            const distance = coordinates ? distanceTo(Number(button.dataset.lat), Number(button.dataset.lon)) : null;
            button.disabled = busy || locating || saved || distance === null || distance > maxDistance;
            button.querySelector('.distance').textContent = distance === null ? '— กม.' : distance.toFixed(2) + ' กม.';
            button.querySelector('.availability').textContent = distance === null ? 'รอตำแหน่ง GPS' : distance > maxDistance ? 'อยู่นอกระยะลงเวลา' : 'ลงเวลาได้';
        });
        submit.disabled = busy || locating || saved || !coordinates || !place;
    }
    function resetConfirmation() { confirmCheckout = false; warning.hidden = true; submit.textContent = 'ยืนยันลงเวลา'; }
    function locate() {
        if (busy || locating || saved) return;
        coordinates = null;
        resetConfirmation();
        locating = true;
        retry.disabled = true;
        update();
        status.textContent = 'กำลังรับตำแหน่ง กรุณาอนุญาต GPS…';
        function fail(error) {
            locating = false; retry.disabled = false; update();
            status.textContent = error.code === 1 ? 'ไม่ได้รับอนุญาตให้ใช้ตำแหน่ง กรุณาเปิดสิทธิ์ตำแหน่งให้ LINE หรือเบราว์เซอร์ แล้วลองอีกครั้ง' : 'ไม่สามารถรับตำแหน่งได้ กรุณาลองอีกครั้ง หรือเปิดในเบราว์เซอร์';
            browser.hidden = false;
        }
        if (!navigator.geolocation) { fail({}); return; }
        navigator.geolocation.getCurrentPosition(position => {
            locating = false; retry.disabled = false;
            coordinates = {lat: position.coords.latitude, lon: position.coords.longitude};
            acquiredAt = Date.now();
            status.textContent = 'ได้รับตำแหน่งแล้ว · ความแม่นยำประมาณ ' + Math.round(position.coords.accuracy) + ' เมตร';
            browser.hidden = true;
            update();
        }, fail, {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
    }
    locations.forEach(button => button.addEventListener('click', () => {
        if (button.disabled) return;
        if (Date.now() - acquiredAt > 60000) { locate(); return; }
        place = button.dataset.place;
        resetConfirmation();
        document.getElementById('selected-place').textContent = button.querySelector('strong').textContent;
        saveStatus.textContent = 'ระบบจะบันทึกเวลาปัจจุบันเมื่อคุณยืนยัน';
        update();
        dialog.showModal();
    }));
    retry.addEventListener('click', locate);
    close.addEventListener('click', () => {
        if (busy) return;
        if (saved) window.location.assign(config.home); else dialog.close();
    });
    dialog.addEventListener('cancel', event => { if (busy || saved) event.preventDefault(); });
    browser.addEventListener('click', () => {
        const url = new URL(config.home, window.location.origin).href;
        if (window.liff && liff.isInClient()) liff.openWindow({url, external: true});
        else { const external = new URL(url); external.searchParams.set('openExternalBrowser', '1'); window.open(external.href, '_blank', 'noopener'); }
    });
    submit.addEventListener('click', async () => {
        if (submit.disabled) return;
        if (Date.now() - acquiredAt > 60000) { dialog.close(); locate(); return; }
        busy = true; update(); retry.disabled = close.disabled = true;
        saveStatus.textContent = 'กำลังบันทึกเวลา…';
        try {
            const response = await fetch(config.endpoint, {
                method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': config.csrf},
                body: JSON.stringify({data: {...coordinates, place: place, confirm_checkout: confirmCheckout}})
            });
            const data = await response.json().catch(() => null);
            if (response.status === 409 && data && data.message === 'checkout_confirmation_required') {
                warning.textContent = 'ทำงานแล้วประมาณ ' + data.workedHours + ' ชั่วโมง ต้องการยืนยันออกงานหรือไม่?';
                warning.hidden = false; confirmCheckout = true;
                submit.textContent = 'ยืนยันออกงาน';
                saveStatus.textContent = 'ยังไม่ได้บันทึกออกงาน กรุณายืนยันหรือปิดเพื่อยกเลิก';
                return;
            }
            if (!response.ok || !data || data.message !== 'success') {
                throw new Error(data && data.message || 'บันทึกไม่สำเร็จ กรุณาปิดแล้วเปิด Connect อีกครั้งเพื่อตรวจสอบสถานะ');
            }
            saved = true;
            const time = new Date(data.time).toLocaleTimeString('th-TH', {timeZone: 'Asia/Bangkok', hour12: false});
            saveStatus.textContent = (data.activity === 'checked out' ? 'บันทึกออกงานแล้ว' : data.activity === 'checked in' ? 'บันทึกเข้างานแล้ว' : 'บันทึกเวลาแล้ว') + ' · ' + time + ' น.';
            submit.hidden = retry.hidden = true;
            close.textContent = 'เสร็จสิ้น';
        } catch (error) {
            // Never retry a write automatically: it may already have reached the server.
            saveStatus.textContent = error.message || 'การเชื่อมต่อขัดข้อง กรุณาตรวจสอบประวัติก่อนลงเวลาอีกครั้ง';
        } finally {
            busy = false; retry.disabled = close.disabled = false; update();
        }
    });
})();
