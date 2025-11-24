// --- Global State ---
let currentLogsPage = 1,
  currentUrlsPage = 1,
  latencyChart = null;

// --- Theme Management ---
function initTheme() {
  const theme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', theme);
  updateThemeToggleIcon(theme);
}

function updateThemeToggleIcon(theme) {
  const icon = document.getElementById('themeToggle').querySelector('i');
  if (theme === 'dark') {
    icon.className = 'ri-moon-line';
  } else {
    icon.className = 'ri-sun-line';
  }
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
  updateThemeToggleIcon(newTheme);
  
  // Update chart theme if it exists
  if (latencyChart) {
    const gridColor = newTheme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)';
    const tickColor = newTheme === 'dark' ? '#8B949E' : '#6B7280';
    latencyChart.options.scales.y.grid.color = gridColor;
    latencyChart.options.scales.x.grid.color = gridColor;
    latencyChart.options.scales.y.ticks.color = tickColor;
    latencyChart.options.scales.x.ticks.color = tickColor;
    latencyChart.update();
  }
}

// --- Init & Event Listeners ---
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  loadLastLogs();
  loadUrlsList();

  document.getElementById("themeToggle").addEventListener("click", toggleTheme);
  document.getElementById("checkButton").addEventListener("click", checkLatency);

  document.getElementById("urlInput").addEventListener("keypress", e => {
    if (e.key === "Enter") checkLatency();
  });

  document.addEventListener("click", function(event) {
    const clickableTarget = event.target.closest(".url-tag, .log-row");
    if (clickableTarget) {
      const url = clickableTarget.dataset.url;
      const headerName = clickableTarget.dataset.headerName;
      const headerValue = clickableTarget.dataset.headerValue;
      if (url) {
        document.getElementById("urlInput").value = url;
        document.getElementById("headerNameInput").value = headerName || "";
        document.getElementById("headerValueInput").value = headerValue || "";
        loadChartData(url);
      }
    }
  });
});

// --- API Calls ---
async function checkLatency() {
  const url = document.getElementById("urlInput").value;
  const headerName = document.getElementById("headerNameInput").value;
  const headerValue = document.getElementById("headerValueInput").value;
  const button = document.getElementById("checkButton");
  const buttonText = button.querySelector("span");

  if (!url) {
    alert("Please enter a URL.");
    return;
  }

  button.disabled = true;
  buttonText.textContent = "Checking...";
  button.querySelector("i").className = "ri-loader-4-line ri-spin";

  try {
    const response = await fetch("/check_api", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: url,
        header_name: headerName,
        header_value: headerValue,
      }),
    });
    const data = await response.json();
    displayResult(data);
    loadChartData(url);
    loadLastLogs(); // Refresh logs
    loadUrlsList(); // Refresh URL list
  } catch (error) {
    displayResult({
      error: "Failed to connect to the server or API. " + error,
      status_code: "NET ERR",
      up: false,
    });
  } finally {
    button.disabled = false;
    buttonText.textContent = "Check API";
    button.querySelector("i").className = "ri-play-line";
  }
}

async function loadLastLogs(page = 1) {
  currentLogsPage = page;
  try {
    const response = await fetch(`/last_logs?page=${page}`);
    const data = await response.json();
    renderLogs(data.logs);
    renderPagination("logs-pagination", data.total_pages, data.current_page, loadLastLogs);
  } catch (error) {
    console.error("Failed to load logs:", error);
  }
}

async function loadUrlsList(page = 1) {
  currentUrlsPage = page;
  try {
    const response = await fetch(`/monitored_urls?page=${page}`);
    const data = await response.json();
    renderUrlsList(data.urls_data);
    // Assuming monitored_urls might get pagination later
    // renderPagination("urls-pagination", data.total_pages, data.current_page, loadUrlsList);
  } catch (error) {
    console.error("Failed to load URLs:", error);
  }
}

async function loadChartData(url) {
  try {
    const response = await fetch(`/chart_data?url=${encodeURIComponent(url)}`);
    const data = await response.json();
    renderChart(data.labels, data.data);
  } catch (error) {
    console.error("Failed to load chart data:", error);
  }
}

// --- Render Functions ---
function renderLogs(logs) {
  const logsContainer = document.querySelector(".log-table tbody");
  if (logs.length === 0) {
    logsContainer.innerHTML = `<tr class="placeholder"><td colspan="5">No logs yet.</td></tr>`;
    return;
  }
  logsContainer.innerHTML = logs.map(log => {
      const status = log.up ? "up" : "down";
      const timestamp = new Date(log.timestamp).toLocaleString();
      return `
      <tr class="log-row" data-url="${log.api_url}" data-header-name="${log.header_name || ''}" data-header-value="${log.header_value || ''}" style="cursor: pointer;">
        <td><span class="log-status ${status === 'up' ? 'success' : 'error'}"><i class="ri-${status === 'up' ? 'checkbox-circle' : 'close-circle'}-fill"></i> ${status.toUpperCase()}</span></td>
        <td title="${log.api_url}">${log.api_url}</td>
        <td>${log.status_code || "N/A"}</td>
        <td>${formatLatency(log.total_latency_ms)}</td>
        <td>${timestamp}</td>
      </tr>
    `;
    }).join("");
  
  // Add click event listeners to all log rows
  document.querySelectorAll('.log-row').forEach(row => {
    row.addEventListener('click', function() {
      const url = this.dataset.url;
      const headerName = this.dataset.headerName;
      const headerValue = this.dataset.headerValue;
      
      // Fill the input fields
      document.getElementById('urlInput').value = url;
      document.getElementById('headerNameInput').value = headerName || '';
      document.getElementById('headerValueInput').value = headerValue || '';
      
      // Automatically trigger the check
      checkLatency();
    });
  });
}

function renderUrlsList(urlsData) {
  const urlsList = document.getElementById("urls-list");
  if (urlsData.length === 0) {
    urlsList.innerHTML = `<p class="placeholder">No URLs monitored yet.</p>`;
    return;
  }
  urlsList.innerHTML = urlsData.map(data => {
      const status = data.up ? "up" : "down";
      return `
      <div class="url-item" data-url="${data.api_url}" data-header-name="${data.header_name || ''}" data-header-value="${data.header_value || ''}">
        <div class="url-text">${data.api_url}</div>
      </div>
    `;
    }).join("");
  
  // Add click event listeners to all URL items
  document.querySelectorAll('.url-item').forEach(item => {
    item.addEventListener('click', function() {
      const url = this.dataset.url;
      const headerName = this.dataset.headerName;
      const headerValue = this.dataset.headerValue;
      
      // Remove active class from all items
      document.querySelectorAll('.url-item').forEach(i => i.classList.remove('active'));
      // Add active class to clicked item
      this.classList.add('active');
      
      // Fill the input fields
      document.getElementById('urlInput').value = url;
      document.getElementById('headerNameInput').value = headerName || '';
      document.getElementById('headerValueInput').value = headerValue || '';
      
      // Automatically trigger the check
      checkLatency();
    });
  });
}

function renderPagination(containerId, totalPages, currentPage, callback) {
  const container = document.getElementById(containerId);
  if (totalPages <= 1) {
    container.innerHTML = "";
    return;
  }
  let buttons = "";
  for (let i = 1; i <= totalPages; i++) {
    buttons += `<button class="${i === currentPage ? "active" : ""}" data-page="${i}">${i}</button>`;
  }
  container.innerHTML = `
    <button data-page="${currentPage - 1}" ${currentPage === 1 ? "disabled" : ""}>Prev</button>
    ${buttons}
    <button data-page="${currentPage + 1}" ${totalPages === currentPage ? "disabled" : ""}>Next</button>
  `;
  container.querySelectorAll("button").forEach(button => {
    button.addEventListener("click", () => {
      const page = parseInt(button.dataset.page, 10);
      if (page) callback(page);
    });
  });
}

function renderChart(labels, data) {
  const ctx = document.getElementById("latencyChart").getContext("2d");
  const theme = document.documentElement.getAttribute('data-theme') || 'light';
  const gridColor = theme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)';
  const tickColor = theme === 'dark' ? '#8B949E' : '#6B7280';
  
  if (latencyChart) {
    latencyChart.destroy();
  }
  latencyChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels.map(l => new Date(l).toLocaleTimeString()),
      datasets: [
        {
          label: "Latency (ms)",
          data: data,
          borderColor: "#4f46e5",
          backgroundColor: "rgba(79, 70, 229, 0.1)",
          fill: true,
          tension: 0.4,
          pointBackgroundColor: "#4f46e5",
          pointRadius: 4,
          pointHoverRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: gridColor },
          ticks: { color: tickColor },
        },
        x: {
          grid: { color: gridColor },
          ticks: { color: tickColor },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
            backgroundColor: '#111827',
            titleFont: { size: 14, weight: 'bold' },
            bodyFont: { size: 12 },
            padding: 10,
            cornerRadius: 6,
        }
      },
    },
  });
}

function displayResult(data) {
  const resultDiv = document.getElementById("result");
  const format = ms => (ms === null || ms === undefined ? "N/A" : ms.toFixed(2));
  const status = data.up ? "up" : "down";
  
  let certHtml = "";
  if (data.certificate_details && !data.certificate_details.error) {
    certHtml = `
      <h4>TLS Certificate</h4>
      <p><strong>Subject:</strong> ${data.certificate_details.subject}</p>
      <p><strong>Issuer:</strong> ${data.certificate_details.issuer}</p>
      <p><strong>Expires:</strong> ${new Date(data.certificate_details.valid_until).toLocaleString()}</p>
    `;
  } else if (data.certificate_details && data.certificate_details.error) {
     certHtml = `<p><strong>Certificate:</strong> Not applicable or check failed.</p>`;
  }

  resultDiv.innerHTML = `
    <div class="result-header">
      <h3 title="${data.api_url}">${data.api_url || "Result"}</h3>
      <span class="status-badge ${status === 'up' ? 'success' : 'error'}">
        <i class="ri-${status === 'up' ? 'checkbox-circle' : 'close-circle'}-line"></i>
        ${data.status_code || "ERR"} (${status.toUpperCase()})
      </span>
    </div>
    <div class="result-details">
        <div class="detail-item">
          <span class="detail-label">Total</span>
          <span class="detail-value">${format(data.total_latency_ms)} ms</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">DNS</span>
          <span class="detail-value">${format(data.dns_latency_ms)} ms</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">TCP Connect</span>
          <span class="detail-value">${format(data.tcp_latency_ms)} ms</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">TLS Handshake</span>
          <span class="detail-value">${format(data.tls_latency_ms)} ms</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Server Processing</span>
          <span class="detail-value">${format(data.server_processing_latency_ms)} ms</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">Content Download</span>
          <span class="detail-value">${format(data.content_download_latency_ms)} ms</span>
        </div>
    </div>
    ${certHtml ? `<div style="margin-top: 1rem; padding: 1rem; background: var(--bg-secondary); border-radius: var(--radius-md); border: 1px solid var(--border-color);">${certHtml}</div>` : ''}
    ${
      data.error
        ? `<div style="margin-top: 1rem; padding: 1rem; background: rgba(239, 68, 68, 0.1); border-radius: var(--radius-md); border: 2px solid var(--danger); color: var(--danger);"><strong>Error:</strong> ${data.error}</div>`
        : ""
    }
  `;
}

function formatLatency(ms) {
    return ms === null || ms === undefined ? "N/A" : `${ms.toFixed(2)} ms`;
}