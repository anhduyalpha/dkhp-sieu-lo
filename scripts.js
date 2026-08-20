(async () => {
  const t0 = performance.now();
  const TARGETS = new Set([
    // Nhập các mã môn cần đăng ký vào đây, ví dụ: "IT001.N11", "IT002.N12"
  ].map(c => c.trim().toUpperCase()));

  const rows = document.querySelectorAll("table tbody tr");
  if (rows.length === 0) {
    console.warn("Chưa tìm thấy bảng học phần trên trang!");
    return;
  }

  let ticked = 0;
  rows.forEach(row => {
    const cells = row.querySelectorAll("td");
    if (cells.length < 2) continue;

    let matchCode = null;
    for (let c = 1; c < Math.min(cells.length, 5); c++) {
      const fullText = (cells[c].innerText || cells[c].textContent || "").trim().toUpperCase();
      const firstWord = fullText.split(/[\s\n\r\t\-]+/)[0];
      if (TARGETS.has(fullText)) { matchCode = fullText; break; }
      if (TARGETS.has(firstWord)) { matchCode = firstWord; break; }
    }

    if (matchCode) {
      const cb = row.querySelector("input[type='checkbox']") || (cells[0] ? cells[0].querySelector("input") : null);
      const chakraLabel = row.querySelector("label.chakra-checkbox, span.chakra-checkbox__control") || (cells[0] ? cells[0].querySelector("label, span") : null);

      if (cb) {
        if (!cb.checked) {
          cb.click();
          if (!cb.checked && chakraLabel) {
            chakraLabel.click();
          }
          if (!cb.checked && cells[0]) {
            cells[0].click();
          }
          if (!cb.checked) {
            cb.checked = true;
            cb.dispatchEvent(new Event('input', { bubbles: true }));
            cb.dispatchEvent(new Event('change', { bubbles: true }));
          }
          ticked++;
        }
      } else if (chakraLabel) {
        chakraLabel.click();
        ticked++;
      } else if (cells[0]) {
        cells[0].click();
        ticked++;
      }
    }
  });

  const findBtn = () => {
    const direct = [
      "div.detailBar button.chakra-button.css-kyhdse",
      "div.detailBar button.chakra-button",
      "div.detailBar button",
      "div[class*='detailBar'] button",
      "button.chakra-button.css-kyhdse",
      "button[type='submit']",
      "form button[type='submit']",
      "button.chakra-button"
    ];
    for (const s of direct) {
      const el = document.querySelector(s);
      if (el) return el;
    }

    const allButtons = Array.from(document.querySelectorAll("button, input[type='submit'], div[role='button'], a[role='button']"));
    for (const b of allButtons) {
      const txt = (b.innerText || b.textContent || b.value || "").trim().toLowerCase();
      if (txt.includes("đăng ký") || txt.includes("dang ky") || txt.includes("lưu") || txt.includes("xác nhận") || txt.includes("submit")) {
        return b;
      }
    }
    return null;
  };

  const doClick = (btn) => {
    if (!btn) return false;
    btn.removeAttribute('disabled');
    btn.disabled = false;
    btn.removeAttribute('aria-disabled');
    btn.style.pointerEvents = 'auto';
    try {
      btn.scrollIntoView({ behavior: "instant", block: "center" });
    } catch(e) {}

    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {
      btn.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
    });
    if (typeof btn.click === 'function') {
      try { btn.click(); } catch(e) {}
    }
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
  } else {
    // Chờ MutationObserver kích hoạt ngay khi React cập nhật DOM (0-30ms)
    await new Promise((resolve) => {
      let done = false;
      const obs = new MutationObserver(() => {
        const b = findBtn();
        if (b && !done) {
          done = true;
          obs.disconnect();
          doClick(b);
          resolve(true);
        }
      });
      try {
        obs.observe(document.body, { childList: true, subtree: true, attributes: true });
      } catch(e) {}

      const poll = setInterval(() => {
        const b = findBtn();
        if (b && !done) {
          done = true;
          clearInterval(poll);
          obs.disconnect();
          doClick(b);
          resolve(true);
        }
      }, 4);

      setTimeout(() => {
        if (!done) {
          done = true;
          clearInterval(poll);
          obs.disconnect();
          const b = findBtn();
          if (b) doClick(b);
          resolve(true);
        }
      }, 150);
    });
  }

  [20, 50, 100].forEach(delay => {
    setTimeout(() => {
      const b = findBtn();
      if (b) doClick(b);
    }, delay);
  });

  console.log(`Đã tick ${ticked} môn và kích hoạt ĐĂNG KÝ tức thì trong ${(performance.now() - t0).toFixed(2)}ms!`);
})();