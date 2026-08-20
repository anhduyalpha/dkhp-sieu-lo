(() => {
  const t0 = performance.now();
  const TARGETS = new Set([
    // Nhập các mã môn cần đăng ký vào đây, ví dụ: "IT001.N11", "IT002.N12"
  ].map(c => c.trim().toUpperCase()));

  const rows = document.querySelectorAll("table tbody tr");
  if (rows.length === 0) {
    console.warn("Chưa tìm thấy bảng học phần trên trang!");
    return;
  }

  const setCheckbox = (cb) => {
    if (!cb) return false;
    if (!cb.checked) {
      try {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'checked')?.set;
        if (setter) setter.call(cb, true);
        else cb.checked = true;
      } catch(e) {
        cb.checked = true;
      }
      cb.dispatchEvent(new Event('input', { bubbles: true }));
      cb.dispatchEvent(new Event('change', { bubbles: true }));
      cb.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      return true;
    }
    return false;
  };

  let ticked = 0;
  rows.forEach(row => {
    const cells = row.querySelectorAll("td");
    if (cells.length < 2) return;
    const code = (cells[1].textContent || "").trim().toUpperCase();

    if (TARGETS.has(code)) {
      const cb = row.querySelector("input[type='checkbox']") || cells[0].querySelector("input");
      if (cb) {
        if (setCheckbox(cb)) {
          ticked++;
        }
      } else {
        cells[0].click();
        ticked++;
      }
    }
  });

  const findBtn = () => {
    const direct = document.querySelector("div.detailBar button, div.detailBar button.chakra-button, button.chakra-button.css-kyhdse, button[type='submit']");
    if (direct) return direct;
    const allButtons = document.querySelectorAll("button, input[type='submit'], div[role='button']");
    for (let i = 0; i < allButtons.length; i++) {
      const txt = (allButtons[i].textContent || allButtons[i].value || "").trim().toLowerCase();
      if (txt.includes("đăng ký") || txt.includes("dang ky") || txt.includes("lưu") || txt.includes("xác nhận")) {
        return allButtons[i];
      }
    }
    return null;
  };

  const doClick = (btn) => {
    if (!btn) return false;
    btn.removeAttribute('disabled');
    btn.disabled = false;
    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {
      btn.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
    });
    if (typeof btn.click === 'function') btn.click();
    const form = btn.closest('form') || document.querySelector('form');
    if (form) {
      try {
        if (typeof form.requestSubmit === 'function') form.requestSubmit(btn);
        else form.dispatchEvent(new Event('submit', { bubbles: true }));
      } catch(e) {}
    }
    return true;
  };

  let btn = findBtn();
  if (btn) {
    doClick(btn);
  }

  // Micro-burst trigger to click instantly as soon as React updates
  [5, 15, 30, 60, 100].forEach(delay => {
    setTimeout(() => {
      const b = findBtn();
      if (b) doClick(b);
    }, delay);
  });

  console.log(`Đã tick ${ticked} môn và bấm ĐĂNG KÝ tức thì trong ${(performance.now() - t0).toFixed(2)}ms!`);
})();