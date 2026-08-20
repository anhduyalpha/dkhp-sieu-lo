(() => {
  const t0 = performance.now();
  const TARGETS = new Set([
    "IT012.R11", "IT012.R11.1", "SS007.R15", "SS003.R14",
    "IT005.R18", "IT005.R18.2", "IT007.R111.1", "IT007.R111",
    "IT004.R117", "IT004.R117.1"
  ].map(c => c.trim().toUpperCase()));

  const rows = document.querySelectorAll("table tbody tr");
  if (rows.length === 0) {
    console.warn("Chưa tìm thấy bảng học phần trên trang!");
    return;
  }

  let ticked = 0;
  rows.forEach(row => {
    const cells = row.querySelectorAll("td");
    if (cells.length < 2) return;
    const code = (cells[1].innerText || cells[1].textContent || "").trim().toUpperCase();

    if (TARGETS.has(code)) {
      const cb = row.querySelector("input[type='checkbox']") || cells[0].querySelector("input");
      if (cb) {
        if (!cb.checked) {
          cb.click();
          cb.dispatchEvent(new Event('change', { bubbles: true }));
          ticked++;
        }
      } else {
        cells[0].click();
        ticked++;
      }
    }
  });

  const btn = 
    document.querySelector("div.detailBar button.chakra-button.css-kyhdse") ||
    document.querySelector("div.detailBar button") ||
    Array.from(document.querySelectorAll("button")).find(b => (b.innerText || "").includes("Đăng ký"));

  if (btn) {
    btn.scrollIntoView({ behavior: "instant", block: "center" });
    btn.click();
    console.log(`Đã tick ${ticked} môn và bấm ĐĂNG KÝ trong ${(performance.now() - t0).toFixed(2)}ms!`);
  } else {
    console.log(`Đã tick ${ticked} môn nhưng không thấy nút Đăng ký!`);
  }
})();