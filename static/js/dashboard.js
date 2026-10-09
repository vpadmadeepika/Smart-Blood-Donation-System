/**
 * Dashboard & Analytics Visualizations using Chart.js
 */

function initAdminCharts(bgData, statusData) {
  // 1. Blood Group Inventory Doughnut Chart
  const bgCtx = document.getElementById('bgInventoryChart');
  if (bgCtx && bgData) {
    new Chart(bgCtx, {
      type: 'doughnut',
      data: {
        labels: Object.keys(bgData),
        datasets: [{
          data: Object.values(bgData),
          backgroundColor: [
            '#dc2626', '#ef4444', '#f87171', '#fca5a5',
            '#0284c7', '#38bdf8', '#10b981', '#34d399'
          ],
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { boxWidth: 12, font: { family: 'Plus Jakarta Sans', size: 12 } }
          }
        },
        cutout: '68%'
      }
    });
  }

  // 2. Request Status Bar Chart
  const statusCtx = document.getElementById('requestStatusChart');
  if (statusCtx && statusData) {
    new Chart(statusCtx, {
      type: 'bar',
      data: {
        labels: Object.keys(statusData),
        datasets: [{
          label: 'Requests Count',
          data: Object.values(statusData),
          backgroundColor: '#ef4444',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0, font: { family: 'Plus Jakarta Sans' } },
            grid: { color: '#f1f5f9' }
          },
          x: {
            ticks: { font: { family: 'Plus Jakarta Sans', size: 11 } },
            grid: { display: false }
          }
        }
      }
    });
  }
}

// Client-side quick filter for tables
function filterTable(inputId, tableId) {
  const input = document.getElementById(inputId);
  const table = document.getElementById(tableId);
  if (!input || !table) return;

  input.addEventListener('keyup', () => {
    const filter = input.value.toLowerCase();
    const rows = table.getElementsByTagName('tr');

    for (let i = 1; i < rows.length; i++) {
      const text = rows[i].textContent.toLowerCase();
      rows[i].style.display = text.indexOf(filter) > -1 ? '' : 'none';
    }
  });
}
