document.addEventListener('DOMContentLoaded', function () {
  const selectAll = document.getElementById('select-all');
  const generateBtn = document.getElementById('generate-btn');
  const checkboxes = () => document.querySelectorAll('.order-checkbox');

  if (selectAll) {
    selectAll.addEventListener('change', function () {
      checkboxes().forEach(cb => cb.checked = this.checked);
      updateButton();
    });
  }

  document.addEventListener('change', function (e) {
    if (e.target.classList.contains('order-checkbox')) updateButton();
  });

  function updateButton() {
    const any = [...checkboxes()].some(cb => cb.checked);
    if (generateBtn) generateBtn.disabled = !any;
  }

  if (generateBtn) {
    generateBtn.addEventListener('click', async function () {
      const ids = [...checkboxes()]
        .filter(cb => cb.checked)
        .map(cb => cb.dataset.orderId);
      if (!ids.length) return;

      generateBtn.disabled = true;
      generateBtn.textContent = 'Generating...';

      try {
        const resp = await fetch('/api/orders/generate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({order_ids: ids})
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Failed');
        const host = document.getElementById('host-value')?.value || '';
        window.location.href = `/downloads?job_id=${data.job_id}&host=${encodeURIComponent(host)}`;
      } catch (err) {
        alert('Error: ' + err.message);
        generateBtn.disabled = false;
        generateBtn.textContent = 'Generate Print Files';
      }
    });
  }
});
