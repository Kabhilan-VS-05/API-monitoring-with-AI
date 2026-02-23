document.addEventListener("DOMContentLoaded", () => {
  // --- Element Refs ---
  const mainView = document.getElementById("mainView");
  const detailsView = document.getElementById("detailsView");
  const monitorListDiv = document.getElementById("monitorList"); // This will now correctly find the element
  const addApiModal = document.getElementById("addApiModal");
  const reportModal = document.getElementById("reportModal");
  const addApiForm = document.getElementById("addApiForm");
  const addApiBtn = document.getElementById("addApiBtn");
  const cancelBtn = document.getElementById("cancelBtn");
  const modalTitle = document.getElementById("modalTitle");
  const modalSubmitBtn = document.getElementById("modalSubmitBtn");
  const apiEditId = document.getElementById("apiEditId");
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const authBtn = document.getElementById('authBtn');
  const sloTotalMonitors = document.getElementById('sloTotalMonitors');
  const sloAvgUptime = document.getElementById('sloAvgUptime');
  const sloAvgBudget = document.getElementById('sloAvgBudget');
  const sloBurnAlerts = document.getElementById('sloBurnAlerts');
  let detailChart = null;
  const communityPanelBtn = document.getElementById('communityPanelBtn');
  const communityPanel = document.getElementById('communityPanel');
  const closeCommunityPanel = document.getElementById('closeCommunityPanel');
  const contactForm = document.getElementById('contactForm');
  const contactTableBody = document.getElementById('contactTableBody');
  const translationBtns = document.querySelectorAll('.translation-btn');
  const translateMessageInput = document.getElementById('translateMessage');
  const translationOutput = document.getElementById('translationOutput');
  const translateClear = document.getElementById('translateClear');
  const preferredLanguageRadios = document.querySelectorAll('input[name="preferredLanguage"]');
  const testAlertApi = document.getElementById('testAlertApi');
  const testAlertChannel = document.getElementById('testAlertChannel');
  const testAlertMessage = document.getElementById('testAlertMessage');
  const sendTestAlert = document.getElementById('sendTestAlert');
  const testAlertStatus = document.getElementById('testAlertStatus');
  const notificationTimeline = document.getElementById('notificationTimeline');
  const refreshTimeline = document.getElementById('refreshTimeline');
  const alertPreviewModal = document.getElementById('alertPreviewModal');
  const closeAlertPreview = document.getElementById('closeAlertPreview');
  const previewTabs = document.querySelectorAll('.preview-tab');
  const previewContent = document.getElementById('previewContent');
  const workerResponsesModal = document.getElementById('workerResponsesModal');
  const closeWorkerResponses = document.getElementById('closeWorkerResponses');
  const workerResponsesBody = document.getElementById('workerResponsesBody');
  const viewFullTimeline = document.getElementById('viewFullTimeline');
  const communityPanelBackdrop = document.getElementById('communityPanelBackdrop');

  function updateBodyScrollLock() {
    const overlayIds = [
      "addApiModal",
      "reportModal",
      "aiInsightsModal",
      "trainingHistoryModal",
      "tokenHelpModal",
      "alertPreviewModal",
      "workerResponsesModal",
      "communityPanel"
    ];
    const shouldLock = overlayIds.some((id) => {
      const el = document.getElementById(id);
      return el && !el.classList.contains("hidden");
    });
    document.body.classList.toggle("scroll-locked", shouldLock);
  }

  // --- Theme Handling ---
  function setIconForTheme(theme) {
    if (theme === 'dark') {
      themeToggleBtn.innerHTML = `<i class="ri-sun-line" style="font-size: 1.25rem;"></i>`;
      themeToggleBtn.setAttribute("aria-label", "Switch to light mode");
    } else {
      themeToggleBtn.innerHTML = `<i class="ri-moon-line" style="font-size: 1.25rem;"></i>`;
      themeToggleBtn.setAttribute("aria-label", "Switch to dark mode");
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    setIconForTheme(theme);
  }

  themeToggleBtn.addEventListener('click', () => {
    const currentTheme = localStorage.getItem('theme') || 'dark'; // Default to dark
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    applyTheme(newTheme);
  });

  // Apply initial theme
  const initialTheme = localStorage.getItem('theme') || 'dark';
  applyTheme(initialTheme);


  const communityStorageKey = 'communityContacts';
  const preferredLanguageKey = 'preferredLanguage';
  let communityContacts = JSON.parse(localStorage.getItem(communityStorageKey)) || [];
  let latestMonitors = [];
  let currentSubscription = {
    plan: 'free',
    features: {
      premium_frequency_locked: true,
      community_communication_enabled: false
    }
  };

  function applySubscriptionUI() {
    const freqSelect = document.getElementById("apiFrequency");
    if (freqSelect) {
      const premiumLocked = currentSubscription?.features?.premium_frequency_locked !== false;
      Array.from(freqSelect.options).forEach(opt => {
        const isPremium = opt.dataset && opt.dataset.premium === "true";
        opt.disabled = !!(isPremium && premiumLocked);
      });
      if (premiumLocked && freqSelect.selectedOptions?.[0]?.dataset?.premium === "true") {
        freqSelect.value = "1";
      }
    }
  }

  function renderContacts() {
    if (!contactTableBody) return;
    contactTableBody.innerHTML = communityContacts.map((contact, idx) => `
      <tr>
        <td>${contact.name}</td>
        <td>${contact.phone}</td>
        <td>${contact.channel}</td>
        <td>${contact.language}</td>
        <td>${contact.groups}</td>
        <td><button class="button-secondary" onclick="window._removeContact(${idx})">Remove</button></td>
      </tr>`).join('') || '<tr><td colspan="6" class="placeholder">No contacts configured yet.</td></tr>';
  }

  function saveContacts() {
    localStorage.setItem(communityStorageKey, JSON.stringify(communityContacts));
    renderContacts();
  }

  function removeContact(index) {
    communityContacts.splice(index, 1);
    saveContacts();
  }

  window._removeContact = removeContact;

  contactForm?.addEventListener('submit', (event) => {
    event.preventDefault();
    const contact = {
      name: document.getElementById('contactName').value.trim(),
      phone: document.getElementById('contactPhone').value.trim(),
      channel: document.getElementById('contactChannel').value,
      language: document.getElementById('contactLanguage').value,
      groups: document.getElementById('contactGroups').value.trim()
    };
    communityContacts.push(contact);
    contactForm.reset();
    saveContacts();
  });

  translationBtns?.forEach(btn => {
    btn.addEventListener('click', async () => {
      const text = translateMessageInput.value.trim();
      if (!text) {
        translationOutput.textContent = 'Enter text before translating.';
        return;
      }
      const target = btn.dataset.lang;
      translationOutput.textContent = 'Translating...';
      try {
        const resp = await fetch('/utils/translate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, target_language: target })
        });
        const data = await resp.json();
        translationOutput.textContent = data.translated_text || 'Translation not available';
      } catch (error) {
        translationOutput.textContent = 'Translation service error';
      }
    });
  });

  translateClear?.addEventListener('click', () => {
    translationOutput.textContent = 'Translation will appear here.';
  });

  preferredLanguageRadios?.forEach(radio => {
    radio.checked = localStorage.getItem(preferredLanguageKey) === radio.value;
    radio.addEventListener('change', () => {
      localStorage.setItem(preferredLanguageKey, radio.value);
    });
  });

  sendTestAlert?.addEventListener('click', async () => {
    if (!testAlertApi.value) {
      testAlertStatus.textContent = 'Select an API to test.';
      return;
    }
    testAlertStatus.textContent = 'Sending test alert...';
    const channel = testAlertChannel.value;
    const message = testAlertMessage.value.trim() || 'Test alert from Community Communication Panel.';
    try {
      const response = await fetch(`/notify/${channel}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_id: testAlertApi.value,
          alert_id: `test-${Date.now()}`,
          phone_number: '+919000000000',
          message_text: message
        })
      });
      const data = await response.json();
      if (data.success) {
        testAlertStatus.textContent = 'Test alert sent successfully!';
      } else {
        testAlertStatus.textContent = `Failed: ${data.error || 'Unknown error'}`;
      }
    } catch (error) {
      testAlertStatus.textContent = 'Test alert failed to deliver.';
    }
  });

  async function populateTimeline() {
    if (!notificationTimeline || !latestMonitors.length) return;
    try {
      const apiId = latestMonitors[0].id;
      const res = await fetch(`/api/worker-responses/${apiId}?limit=10`);
      const data = await res.json();
      if (!data || data.length === 0) {
        notificationTimeline.innerHTML = '<p class="placeholder">No recent activity.</p>';
        return;
      }
      notificationTimeline.innerHTML = data.map(entry => {
        const time = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : 'just now';
        const statusColor = entry.response === 'FIXED' ? 'green' : entry.response === 'RETRY' ? 'yellow' : entry.response === 'NEED_HELP' ? 'red' : 'yellow';
        return `<div class="timeline-entry ${statusColor}"><span>${time} — ${entry.channel} reply: ${entry.response || 'Alert delivered'} (${entry.api_id})</span><span>${entry.phone_number || 'Unknown'}</span></div>`;
      }).join('');
    } catch (error) {
      console.warn('Timeline load failed', error);
    }
  }

  refreshTimeline?.addEventListener('click', populateTimeline);

  communityPanelBtn?.addEventListener('click', () => {
    if (currentSubscription?.features?.community_communication_enabled !== true) {
      alert('Community Communication is available for subscribers only. Free plan supports email and GitHub issues.');
      return;
    }
    communityPanel?.classList.remove('hidden');
    renderContacts();
    populateTimeline();
    updateBodyScrollLock();
  });

  closeCommunityPanel?.addEventListener('click', () => {
    communityPanel?.classList.add('hidden');
    updateBodyScrollLock();
  });

  function updateTestSelect(monitors) {
    if (!testAlertApi) return;
    testAlertApi.innerHTML = monitors.map(m => `<option value="${m.id}">${m.url}</option>`).join('');
  }

  function setPreviewTab(tab) {
    previewTabs.forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tab));
    previewContent.dataset.activeTab = tab;
  }

  previewTabs?.forEach(btn => {
    btn.addEventListener('click', () => setPreviewTab(btn.dataset.tab));
  });

  closeAlertPreview?.addEventListener('click', () => {
    alertPreviewModal?.classList.add('hidden');
    updateBodyScrollLock();
  });

  closeWorkerResponses?.addEventListener('click', () => {
    workerResponsesModal?.classList.add('hidden');
    updateBodyScrollLock();
  });

  alertPreviewModal?.addEventListener('click', (event) => {
    if (event.target === alertPreviewModal) {
      alertPreviewModal.classList.add('hidden');
      updateBodyScrollLock();
    }
  });

  workerResponsesModal?.addEventListener('click', (event) => {
    if (event.target === workerResponsesModal) {
      workerResponsesModal.classList.add('hidden');
      updateBodyScrollLock();
    }
  });

  viewFullTimeline?.addEventListener('click', () => {
    alert('View full incident timeline in the incidents page.');
  });

  async function showTrainingHistory(apiId) {
    if (!trainingHistoryModal || !trainingHistoryContent) return;

    trainingHistoryContent.innerHTML = `
      <div class="training-history-loading">
        <div class="training-spinner"></div>
        <p style="margin-top: 1rem;">Loading training history...</p>
      </div>
    `;
    trainingHistoryModal.classList.remove('hidden');
    updateBodyScrollLock();

    try {
      const runs = await fetchJsonOrDefault(`/api/ai/training_runs/${apiId}?limit=15`, []);
      if (!runs || runs.length === 0) {
        trainingHistoryContent.innerHTML = '<p class="placeholder">No training runs available yet.</p>';
        return;
      }

      const latestRun = runs[0];
      const latestFailure = typeof latestRun.failure_probability === 'number'
        ? `${(latestRun.failure_probability * 100).toFixed(1)}%`
        : 'N/A';
      const latestConfidence = typeof latestRun.confidence === 'number'
        ? `${(latestRun.confidence * 100).toFixed(1)}%`
        : 'N/A';
      const latestRisk = (latestRun.risk_level || 'unknown').toUpperCase();
      const latestDuration = latestRun.duration_seconds ? `${latestRun.duration_seconds.toFixed(1)}s` : 'N/A';
      const riskFactorsList = Array.isArray(latestRun.risk_factors) && latestRun.risk_factors.length > 0
        ? `<ul class="training-history-factors">${latestRun.risk_factors.map(f => `<li>${escapeHtml(f)}</li>`).join('')}</ul>`
        : '<p class="placeholder">No risk factors captured.</p>';
      const latestSummary = latestRun.summary ? `<p class="training-history-summary">${escapeHtml(latestRun.summary)}</p>` : '';
      const latestActions = Array.isArray(latestRun.actions) && latestRun.actions.length > 0
        ? `<div class="training-history-actions">${latestRun.actions.map(act => `<span>${escapeHtml(act)}</span>`).join('')}</div>`
        : '';

      const continueRuns = runs.slice(1);
      const htmlHistory = continueRuns.map(run => {
        const startedAt = run.started_at ? new Date(run.started_at).toLocaleString() : 'N/A';
        const completedAt = run.completed_at ? new Date(run.completed_at).toLocaleString() : 'N/A';
        const failureProb = typeof run.failure_probability === 'number' ? `${(run.failure_probability * 100).toFixed(1)}%` : 'N/A';
        const confidence = typeof run.confidence === 'number' ? `${(run.confidence * 100).toFixed(1)}%` : 'N/A';
        const riskLevel = (run.risk_level || 'unknown').toUpperCase();
        const status = run.status || 'completed';
        const duration = run.duration_seconds ? `${run.duration_seconds.toFixed(1)}s` : 'N/A';
        const summary = run.summary ? `<p class="training-history-summary">${escapeHtml(run.summary)}</p>` : '';
        const actions = run.actions && run.actions.length
          ? `<div class="training-history-actions">${run.actions.map(act => `<span>${escapeHtml(act)}</span>`).join('')}</div>`
          : '';
        const logs = Array.isArray(run.log_lines) ? run.log_lines.map(line => `<li>${escapeHtml(line)}</li>`).join('') : '';

        return `
          <article class="training-history-entry">
            <header>
              <div>
                <strong>${escapeHtml(startedAt)}</strong>
                <small>${escapeHtml(status)} · ${escapeHtml(riskLevel)}</small>
              </div>
              <div>
                <small>Failure: ${escapeHtml(failureProb)}</small>
                <small>Confidence: ${escapeHtml(confidence)}</small>
                <small>Duration: ${escapeHtml(duration)}</small>
              </div>
            </header>
            <div class="training-history-meta">
              <span>Started: ${escapeHtml(startedAt)}</span>
              <span>Completed: ${escapeHtml(completedAt)}</span>
              <span>Sample Size: ${escapeHtml(String(run.sample_size || run.metrics?.sample_size || 'N/A'))}</span>
            </div>
            ${summary}
            ${actions}
            ${logs ? `<div class="training-history-logs"><p><strong>Log snippet</strong></p><ul>${logs}</ul></div>` : ''}
          </article>
        `;
      }).join('');

      trainingHistoryContent.innerHTML = `
      <section class="training-history-latest">
        <h3>Latest Trained Model</h3>
        <div class="training-history-latest-grid">
          <div>
            <small>Failure Probability</small>
            <strong>${escapeHtml(latestFailure)}</strong>
          </div>
          <div>
            <small>Confidence</small>
            <strong>${escapeHtml(latestConfidence)}</strong>
          </div>
          <div>
            <small>Risk Level</small>
            <strong>${escapeHtml(latestRisk)}</strong>
          </div>
          <div>
            <small>Duration</small>
            <strong>${escapeHtml(latestDuration)}</strong>
          </div>
        </div>
        <div class="training-history-meta">
          <span>Started: ${escapeHtml(latestRun.started_at ? new Date(latestRun.started_at).toLocaleString() : 'N/A')}</span>
          <span>Completed: ${escapeHtml(latestRun.completed_at ? new Date(latestRun.completed_at).toLocaleString() : 'N/A')}</span>
          <span>Sample Size: ${escapeHtml(String(latestRun.sample_size || latestRun.metrics?.sample_size || 'N/A'))}</span>
        </div>
        ${latestSummary}
        ${latestActions}
        <div class="training-history-factors-block">
          <strong>Risk Factors</strong>
          ${riskFactorsList}
        </div>
      </section>
      <section class="training-history-past">
        <h3>Previous Training Runs</h3>
        <div class="training-history-list">
          ${htmlHistory}
        </div>
      </section>
    `;
    } catch (err) {
      console.error('Failed to load training history:', err);
      trainingHistoryContent.innerHTML = '<p class="placeholder error">Unable to load training history.</p>';
    }
  }

  window.showTrainingHistory = showTrainingHistory;

  // --- Developer Data Integration ---
  const settingsBtn = document.getElementById('settingsBtn');
  const devDataPanel = document.getElementById('devDataPanel');
  const closeDevPanel = document.getElementById('closeDevPanel');
  const syncGithubBtn = document.getElementById('syncGithubBtn');
  const exportDatasetBtn = document.getElementById('exportDatasetBtn');
  const createIncidentBtn = document.getElementById('createIncidentBtn');
  const tokenHelpLink = document.getElementById('tokenHelpLink');
  const tokenHelpModal = document.getElementById('tokenHelpModal');
  const closeTokenHelp = document.getElementById('closeTokenHelp');

  // Toggle settings panel (combined single listener)
  if (settingsBtn && devDataPanel) {
    settingsBtn.setAttribute("aria-expanded", "false");
    settingsBtn.addEventListener('click', async () => {
      const willOpen = devDataPanel.classList.contains('hidden');
      devDataPanel.classList.toggle('hidden');
      settingsBtn.setAttribute("aria-expanded", willOpen ? "true" : "false");
      if (willOpen) {
        communityPanel?.classList.add('hidden');
        await loadGitHubSettings();
        loadDataSummary();
        devDataPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      updateBodyScrollLock();
    });
  }

  closeDevPanel?.addEventListener('click', () => {
    devDataPanel?.classList.add('hidden');
    settingsBtn?.setAttribute("aria-expanded", "false");
    updateBodyScrollLock();
  });

  // Token help modal
  tokenHelpLink?.addEventListener('click', (e) => {
    e.preventDefault();
    tokenHelpModal?.classList.remove('hidden');
    updateBodyScrollLock();
  });

  closeTokenHelp?.addEventListener('click', () => {
    tokenHelpModal?.classList.add('hidden');
    updateBodyScrollLock();
  });

  tokenHelpModal?.addEventListener('click', (e) => {
    if (e.target === tokenHelpModal) {
      tokenHelpModal.classList.add('hidden');
      updateBodyScrollLock();
    }
  });

  // Load GitHub settings from database
  async function loadGitHubSettings() {
    try {
      const response = await fetch('/api/github/settings');
      const settings = await response.json();

      if (settings.repo_owner && settings.repo_name) {
        document.getElementById('repoOwner').value = settings.repo_owner;
        document.getElementById('repoName').value = settings.repo_name;
      }

      // Show token status (masked)
      if (settings.has_token) {
        document.getElementById('githubToken').placeholder = `Token saved: ${settings.github_token || '****'}`;
      }
    } catch (error) {
      console.error('Error loading GitHub settings:', error);
    }
  }

  // Sync GitHub data
  syncGithubBtn.addEventListener('click', async () => {
    const repoOwner = document.getElementById('repoOwner').value.trim();
    const repoName = document.getElementById('repoName').value.trim();
    const githubToken = document.getElementById('githubToken').value.trim();
    const sinceDays = parseInt(document.getElementById('sinceDays').value) || 90;
    const syncStatus = document.getElementById('syncStatus');

    if (!repoOwner || !repoName) {
      syncStatus.className = 'sync-status error';
      syncStatus.innerHTML = '<i class="ri-error-warning-line"></i> Please enter repository owner and name';
      return;
    }

    syncStatus.className = 'sync-status loading';
    syncStatus.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Saving settings and syncing GitHub data...';
    syncGithubBtn.disabled = true;

    try {
      // Save GitHub settings first (including token if provided)
      const settingsPayload = {
        repo_owner: repoOwner,
        repo_name: repoName
      };

      if (githubToken) {
        settingsPayload.github_token = githubToken;
      }

      const saveResponse = await fetch('/api/github/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settingsPayload)
      });
      const saveData = await saveResponse.json();

      if (!saveData.success) {
        throw new Error('Failed to save settings');
      }

      // Sync commits and PRs
      const githubResponse = await fetch('/api/sync/github', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_owner: repoOwner, repo_name: repoName, since_days: sinceDays })
      });
      const githubData = await githubResponse.json();

      // Sync issues
      const issueResponse = await fetch('/api/sync/issues', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_owner: repoOwner, repo_name: repoName })
      });
      const issueData = await issueResponse.json();

      if (githubData.success && issueData.success) {
        syncStatus.className = 'sync-status success';
        syncStatus.innerHTML = `<i class="ri-checkbox-circle-line"></i> Settings saved! Synced ${githubData.commits.count} commits, ${githubData.pull_requests.count} PRs, and ${issueData.count} issues`;
        loadDataSummary();
      } else {
        throw new Error('Sync failed');
      }
    } catch (error) {
      syncStatus.className = 'sync-status error';
      syncStatus.innerHTML = `<i class="ri-error-warning-line"></i> Error: ${error.message}`;
    } finally {
      syncGithubBtn.disabled = false;
    }
  });

  // Export monitoring dataset to GitHub
  exportDatasetBtn.addEventListener('click', async () => {
    const exportStatus = document.getElementById('exportStatus');

    exportStatus.className = 'sync-status loading';
    exportStatus.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Exporting monitoring data to GitHub...';
    exportDatasetBtn.disabled = true;

    try {
      const response = await fetch('/api/github/export-dataset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const result = await response.json();

      if (result.success) {
        exportStatus.className = 'sync-status success';
        exportStatus.innerHTML = `<i class="ri-checkbox-circle-line"></i> Dataset exported successfully! <br><i class="ri-bar-chart-line"></i> ${result.records_exported} records exported<br><a href="${result.file_url}" target="_blank" style="color: #58A6FF;">View on GitHub</a>`;
      } else {
        throw new Error(result.error || 'Export failed');
      }
    } catch (error) {
      exportStatus.className = 'sync-status error';
      exportStatus.innerHTML = `<i class="ri-error-warning-line"></i> Error: ${error.message}`;
    } finally {
      exportDatasetBtn.disabled = false;
    }
  });

  // Load data summary
  async function loadDataSummary() {
    try {
      const [commits, issues, incidents, logs] = await Promise.all([
        fetch('/api/commits?hours=168').then(r => r.json()),
        fetch('/api/issues').then(r => r.json()),
        fetch('/api/incidents').then(r => r.json()),
        fetch('/api/logs?hours=24&level=error').then(r => r.json())
      ]);

      const commitCountVal = commits.length || 0;
      const issueCountVal = issues.length || 0;
      const incidentCountVal = incidents.length || 0;
      const logCountVal = logs.length || 0;

      document.getElementById('commitCount').textContent = commitCountVal;
      document.getElementById('issueCount').textContent = issueCountVal;
      document.getElementById('incidentCount').textContent = incidentCountVal;
      document.getElementById('logCount').textContent = logCountVal;

      // Update Dashboard Overview Card
      const devOverview = document.getElementById('developerOverview');
      if (commitCountVal > 0 || issueCountVal > 0) {
        devOverview.classList.remove('hidden');
        document.getElementById('overviewCommits').textContent = commitCountVal;
        document.getElementById('overviewIssues').textContent = issueCountVal;
        document.getElementById('overviewLog').textContent = logCountVal;

        // Fetch repo info
        const repoRes = await fetch('/api/github/settings');
        const settings = await repoRes.json();
        if (settings.repo_owner && settings.repo_name) {
          document.getElementById('repoSlug').textContent = `${settings.repo_owner}/${settings.repo_name}`;
        }
      } else {
        devOverview.classList.add('hidden');
      }

      // Display commits
      displayCommits(commits);
      // Display issues
      displayIssues(issues);
      // Display incidents
      displayIncidents(incidents);
    } catch (error) {
      console.error('Error loading data summary:', error);
    }
  }


  // Display commits list
  function displayCommits(commits) {
    const commitsList = document.getElementById('commitsList');
    if (commits.length === 0) {
      commitsList.innerHTML = '<p class="no-data">No commits synced yet. Click "Sync GitHub Data" above.</p>';
      return;
    }

    commitsList.innerHTML = commits.slice(0, 10).map(commit => {
      const date = new Date(commit.timestamp);
      const timeAgo = getTimeAgo(date);
      const filesHtml = commit.files_changed && commit.files_changed.length > 0
        ? `<div class="data-item-files">${commit.files_changed.slice(0, 5).map(f =>
          `<span class="file-tag">${f}</span>`
        ).join('')}${commit.files_changed.length > 5 ? `<span class="file-tag">+${commit.files_changed.length - 5} more</span>` : ''}</div>`
        : '';

      return `
        <div class="data-item">
          <div class="data-item-header">
            <div class="data-item-title">${escapeHtml(commit.message.split('\n')[0])}</div>
          </div>
          <div class="data-item-meta">
            <span><i class="ri-user-line"></i> ${escapeHtml(commit.author)}</span>
            <span><i class="ri-time-line"></i> ${timeAgo}</span>
            <span><i class="ri-git-commit-line"></i> ${commit.commit_id.substring(0, 7)}</span>
          </div>
          ${filesHtml}
        </div>
      `;
    }).join('');
  }

  // Display issues list
  function displayIssues(issues) {
    const issuesList = document.getElementById('issuesList');
    if (issues.length === 0) {
      issuesList.innerHTML = '<p class="no-data">No issues synced yet.</p>';
      return;
    }

    issuesList.innerHTML = issues.slice(0, 10).map(issue => {
      const date = new Date(issue.created_at);
      const timeAgo = getTimeAgo(date);
      const badgeClass = issue.state === 'open' ? 'badge-open' : 'badge-closed';
      const priorityBadge = issue.priority ? `<span class="data-item-badge badge-${issue.priority}">${issue.priority}</span>` : '';

      return `
        <div class="data-item">
          <div class="data-item-header">
            <div class="data-item-title">#${issue.number}: ${escapeHtml(issue.title)}</div>
            <span class="data-item-badge ${badgeClass}">${issue.state}</span>
          </div>
          <div class="data-item-meta">
            <span><i class="ri-time-line"></i> ${timeAgo}</span>
            ${priorityBadge}
            ${issue.labels && issue.labels.length > 0 ? `<span><i class="ri-price-tag-3-line"></i> ${issue.labels.join(', ')}</span>` : ''}
          </div>
          ${issue.description ? `<div class="data-item-description">${escapeHtml(issue.description.substring(0, 150))}${issue.description.length > 150 ? '...' : ''}</div>` : ''}
        </div>
      `;
    }).join('');
  }

  // Display incidents list
  function displayIncidents(incidents) {
    const incidentsList = document.getElementById('incidentsList');
    if (incidents.length === 0) {
      incidentsList.innerHTML = '<p class="no-data">No incidents created yet.</p>';
      return;
    }

    incidentsList.innerHTML = incidents.slice(0, 10).map(incident => {
      const date = new Date(incident.created_at);
      const timeAgo = getTimeAgo(date);
      const severityBadge = `<span class="data-item-badge badge-${incident.severity}">${incident.severity}</span>`;

      return `
        <div class="data-item">
          <div class="data-item-header">
            <div class="data-item-title">${escapeHtml(incident.title)}</div>
            ${severityBadge}
          </div>
          <div class="data-item-meta">
            <span><i class="ri-hashtag"></i> ${incident.incident_id}</span>
            <span><i class="ri-time-line"></i> ${timeAgo}</span>
            ${incident.created_by ? `<span><i class="ri-user-line"></i> ${escapeHtml(incident.created_by)}</span>` : ''}
          </div>
          ${incident.summary ? `<div class="data-item-description">${escapeHtml(incident.summary)}</div>` : ''}
          ${incident.root_cause ? `<div class="data-item-meta" style="margin-top: 0.5rem;"><span><strong>Root Cause:</strong> ${escapeHtml(incident.root_cause)}</span></div>` : ''}
          ${incident.fix_applied ? `<div class="data-item-meta"><span><strong>Fix:</strong> ${escapeHtml(incident.fix_applied)}</span></div>` : ''}
        </div>
      `;
    }).join('');
  }

  // Helper function to get time ago
  function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    const intervals = {
      year: 31536000,
      month: 2592000,
      week: 604800,
      day: 86400,
      hour: 3600,
      minute: 60
    };

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
      const interval = Math.floor(seconds / secondsInUnit);
      if (interval >= 1) {
        return `${interval} ${unit}${interval > 1 ? 's' : ''} ago`;
      }
    }
    return 'just now';
  }

  // Helper function to escape HTML
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  async function fetchJsonOrDefault(url, defaultValue) {
    try {
      const res = await fetch(url);
      if (!res.ok) {
        console.warn(`AI endpoint ${url} returned status`, res.status);
        return defaultValue;
      }
      return await res.json();
    } catch (e) {
      console.error(`Failed to fetch JSON from ${url}:`, e);
      return defaultValue;
    }
  }

  // --- AI Insights Functions ---
  const aiInsightsModal = document.getElementById('aiInsightsModal');
  const closeAiModal = document.getElementById('closeAiModal');
  const aiInsightsContent = document.getElementById('aiInsightsContent');
  const trainingHistoryModal = document.getElementById('trainingHistoryModal');
  const closeTrainingHistory = document.getElementById('closeTrainingHistory');
  const trainingHistoryContent = document.getElementById('trainingHistoryContent');

  if (closeAiModal) {
    closeAiModal.addEventListener('click', () => {
      aiInsightsModal.classList.add('hidden');
      updateBodyScrollLock();
    });
  }

  if (closeTrainingHistory) {
    closeTrainingHistory.addEventListener('click', () => {
      trainingHistoryModal.classList.add('hidden');
      updateBodyScrollLock();
    });
  }

  // Close modal when clicking outside
  if (aiInsightsModal) {
    aiInsightsModal.addEventListener('click', (e) => {
      if (e.target === aiInsightsModal) {
        aiInsightsModal.classList.add('hidden');
        updateBodyScrollLock();
      }
    });
  }

  if (trainingHistoryModal) {
    trainingHistoryModal.addEventListener('click', (e) => {
      if (e.target === trainingHistoryModal) {
        trainingHistoryModal.classList.add('hidden');
        updateBodyScrollLock();
      }
    });
  }

  async function loadAIInsights(apiId) {
    try {
      // Disable the button to prevent multiple clicks
      const aiButton = event?.target?.closest('.button-ai-insights');
      if (aiButton) {
        aiButton.disabled = true;
        aiButton.style.opacity = '0.5';
        aiButton.style.cursor = 'not-allowed';
      }

      // First, check if training is already in progress
      try {
        const checkStatus = await fetch(`http://localhost:5001/training/status/${apiId}`);
        if (checkStatus.ok) {
          const currentStatus = await checkStatus.json();
          if (currentStatus.status === 'training' || currentStatus.status === 'starting' || currentStatus.status === 'analyzing') {
            alert('AI training is already in progress for this API. Please wait for it to complete.');
            // Re-enable button
            if (aiButton) {
              aiButton.disabled = false;
              aiButton.style.opacity = '1';
              aiButton.style.cursor = 'pointer';
            }
            return;
          }
        }
      } catch (e) {
        // Service might not be running, continue anyway
      }

      aiInsightsModal.classList.remove('hidden');
      updateBodyScrollLock();

      // Show animated training status with progress bar and time estimate
      aiInsightsContent.innerHTML = `
        <div style="text-align: center; padding: 3rem;">
          <div class="training-spinner-container">
            <div class="training-spinner"></div>
            <div class="spinner-pulse"></div>
          </div>
          <h3 style="margin-top: 1.5rem; color: #58A6FF;"><i class="ri-brain-line"></i> AI Model Training</h3>
          <p style="color: #8B949E; margin-top: 0.5rem;">Analyzing historical data and patterns...</p>
          <div id="training-status" style="margin-top: 1rem; color: #58A6FF; font-weight: 600; font-size: 1.1rem;"></div>
          
          <!-- Progress Bar -->
          <div class="training-progress-container" style="margin-top: 2rem;">
            <div class="training-progress-bar">
              <div id="training-progress-fill" class="training-progress-fill"></div>
            </div>
            <div id="training-percentage" style="margin-top: 0.5rem; color: #8B949E; font-size: 0.9rem;">0%</div>
          </div>
          
          <p style="color: #D29922; font-size: 0.9rem; margin-top: 1.5rem; font-weight: 600;">
            <i class="ri-time-line"></i> Estimated Time: 2-5 minutes
          </p>
          <p style="color: #8B949E; font-size: 0.85rem; margin-top: 0.5rem;">
            <i class="ri-information-line"></i> Training runs on separate service (Port 5001)
          </p>
        </div>
      `;

      // Add CSS for advanced spinner and progress animations
      if (!document.getElementById('spinner-style')) {
        const style = document.createElement('style');
        style.id = 'spinner-style';
        style.textContent = `
          .training-spinner-container {
            position: relative;
            width: 80px;
            height: 80px;
            margin: 0 auto;
          }
          
          .training-spinner {
            width: 80px;
            height: 80px;
            border: 5px solid #30363D;
            border-top: 5px solid #58A6FF;
            border-right: 5px solid #58A6FF;
            border-radius: 50%;
            animation: spin 1.5s linear infinite;
            position: relative;
            z-index: 2;
          }
          
          .spinner-pulse {
            position: absolute;
            top: 0;
            left: 0;
            width: 80px;
            height: 80px;
            border: 5px solid #58A6FF;
            border-radius: 50%;
            opacity: 0;
            animation: pulse 2s ease-out infinite;
            z-index: 1;
          }
          
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          
          @keyframes pulse {
            0% {
              transform: scale(1);
              opacity: 0.8;
            }
            50% {
              transform: scale(1.3);
              opacity: 0.4;
            }
            100% {
              transform: scale(1.6);
              opacity: 0;
            }
          }
          
          .training-progress-container {
            max-width: 400px;
            margin: 0 auto;
          }
          
          .training-progress-bar {
            width: 100%;
            height: 12px;
            background: #30363D;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
          }
          
          .training-progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #58A6FF, #1e3a8a, #58A6FF);
            background-size: 200% 100%;
            border-radius: 10px;
            width: 0%;
            transition: width 0.5s ease;
            animation: shimmer 2s linear infinite;
            box-shadow: 0 0 10px rgba(88, 166, 255, 0.5);
          }
          
          @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
          }
          
          .ri-loader-4-line {
            animation: spin 1s linear infinite;
          }
        `;
        document.head.appendChild(style);
      }

      // Get progress elements
      const statusEl = document.getElementById('training-status');
      const progressFill = document.getElementById('training-progress-fill');
      const progressPercentage = document.getElementById('training-percentage');

      // Set initial progress immediately
      if (statusEl) statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Preparing training environment...';
      if (progressFill) progressFill.style.width = '5%';
      if (progressPercentage) progressPercentage.textContent = '5%';

      // Simulated progress animation (smooth increase while waiting for real updates)
      let simulatedProgress = 5;
      let trainingStarted = false;

      const simulateProgress = setInterval(() => {
        if (simulatedProgress < 90 && !progressFill.dataset.realUpdate) {
          // Slow down as we approach higher percentages
          if (simulatedProgress < 30) {
            simulatedProgress += 3;
          } else if (simulatedProgress < 60) {
            simulatedProgress += 2;
          } else {
            simulatedProgress += 1;
          }

          if (progressFill && !progressFill.dataset.realUpdate) {
            progressFill.style.width = simulatedProgress + '%';
            if (progressPercentage) progressPercentage.textContent = simulatedProgress + '%';
          }
        }
      }, 2000); // Update every 2 seconds

      // Create a Promise that resolves when training animation is complete
      const trainingPromise = new Promise(async (resolve, reject) => {
        const trainingStartTime = Date.now();
        const MIN_DISPLAY_TIME = 5000; // Minimum 5 seconds to acknowledge training
        let trainingCompleted = false;
        let currentStatus = 'idle';

        // Trigger training first
        try {
          console.log('[AI] Triggering training...');
          const trainResponse = await fetch('/api/ai/train', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              api_id: apiId,
              force_retrain: true
            })
          });

          if (!trainResponse.ok) {
            clearInterval(simulateProgress);
            reject(new Error('Training service unavailable'));
            return;
          }

          console.log('[AI] Training triggered successfully');
        } catch (error) {
          clearInterval(simulateProgress);
          reject(error);
          return;
        }

        // Poll for status
        const pollStatus = setInterval(async () => {
          try {
            const statusResponse = await fetch(`http://localhost:5001/training/status/${apiId}`);
            if (statusResponse.ok) {
              const status = await statusResponse.json();
              const elapsedTime = Date.now() - trainingStartTime;
              currentStatus = status.status || 'idle';

              console.log(`[AI] Status: ${currentStatus}, Progress: ${progressPercentage.textContent}, Elapsed: ${Math.floor(elapsedTime / 1000)}s`);

              if (statusEl && progressFill && progressPercentage) {
                progressFill.dataset.realUpdate = 'true';

                if (currentStatus === 'starting') {
                  statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Loading historical data...';
                  progressFill.style.width = '15%';
                  progressPercentage.textContent = '15%';
                } else if (currentStatus === 'training') {
                  const trainingProgress = Math.min(20 + (elapsedTime / 1000), 75);
                  const progressPercent = Math.floor(trainingProgress);

                  // Show different messages based on progress
                  if (progressPercent < 30) {
                    statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Preparing training dataset...';
                  } else if (progressPercent < 50) {
                    statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Training LSTM Neural Network...';
                  } else if (progressPercent < 70) {
                    statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Training Autoencoder Model...';
                  } else {
                    statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Validating Model Accuracy...';
                  }

                  progressFill.style.width = progressPercent + '%';
                  progressPercentage.textContent = progressPercent + '%';
                } else if (currentStatus === 'analyzing') {
                  statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Generating AI Predictions...';
                  progressFill.style.width = '85%';
                  progressPercentage.textContent = '85%';
                } else if (currentStatus === 'completed') {
                  trainingCompleted = true;
                  clearInterval(pollStatus);

                  // Immediately jump to 90% if below
                  const currentProgress = parseInt(progressPercentage.textContent) || 80;
                  if (currentProgress < 90) {
                    progressFill.style.width = '90%';
                    progressPercentage.textContent = '90%';
                    statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Finalizing...';
                  }

                  // Fast animate from 90% to 100%
                  const animateToComplete = () => {
                    let progress = 90;
                    const animInterval = setInterval(() => {
                      if (progress < 100) {
                        progress += 5; // Faster increment (5% instead of 2%)
                        if (progress > 100) progress = 100;
                        progressFill.style.width = progress + '%';
                        progressPercentage.textContent = progress + '%';

                        if (progress >= 95) {
                          statusEl.innerHTML = '<i class="ri-loader-4-line"></i> Almost done...';
                        }
                      } else {
                        clearInterval(animInterval);
                        clearInterval(simulateProgress);
                        statusEl.innerHTML = '<i class="ri-checkbox-circle-line"></i> Training Complete!';
                        progressFill.style.background = 'linear-gradient(90deg, #3FB950, #2ea043)';
                        progressPercentage.style.color = '#3FB950';

                        // Ensure minimum display time
                        const totalElapsed = Date.now() - trainingStartTime;
                        const remainingTime = Math.max(0, MIN_DISPLAY_TIME - totalElapsed);

                        console.log(`[AI] Training complete. Total time: ${Math.floor(totalElapsed / 1000)}s, Waiting: ${Math.floor(remainingTime / 1000)}s more`);

                        setTimeout(() => {
                          console.log('[AI] Animation complete, resolving promise');
                          resolve(true);
                        }, remainingTime);
                      }
                    }, 100); // Faster interval (100ms instead of 200ms)
                  };

                  // Start animation immediately
                  animateToComplete();
                } else if (currentStatus === 'error') {
                  clearInterval(pollStatus);
                  clearInterval(simulateProgress);
                  statusEl.innerHTML = '<i class="ri-alert-line"></i> Training Error';
                  progressFill.style.background = '#F85149';
                  reject(new Error('Training error'));
                } else if (currentStatus === 'skipped') {
                  clearInterval(pollStatus);
                  clearInterval(simulateProgress);
                  statusEl.innerHTML = '<i class="ri-alert-line"></i> Insufficient Data';
                  progressFill.style.background = '#D29922';
                  reject(new Error('Insufficient data'));
                }
              }
            }
          } catch (pollError) {
            console.warn('[AI] Status poll error:', pollError);
          }
        }, 2000);

        // Safety timeout
        setTimeout(() => {
          clearInterval(pollStatus);
          clearInterval(simulateProgress);
          if (!trainingCompleted) {
            console.warn('[AI] Training timeout');
            reject(new Error('Training timeout'));
          }
        }, 300000); // 5 minutes max
      });

      // Wait for training to complete
      console.log('[AI] Waiting for training to complete...');
      try {
        await trainingPromise;
        console.log('[AI] Training promise resolved, fetching results...');
      } catch (error) {
        console.error('[AI] Training failed:', error);
        if (statusEl) statusEl.innerHTML = `<i class="ri-alert-line"></i> ${error.message}`;
        // Re-enable button on error
        if (aiButton) {
          aiButton.disabled = false;
          aiButton.style.opacity = '1';
          aiButton.style.cursor = 'pointer';
        }
        return; // Stop here if training failed
      }

      // Wait a moment to show completion message
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Now fetch prediction, anomalies, insights, and stored history in parallel
      const [prediction, anomalies, insights, insightHistory, latestRun, trainingRuns] = await Promise.all([
        fetchJsonOrDefault(`/api/ai/predict/${apiId}`, {
          will_fail: false,
          confidence: 0,
          reason: 'AI prediction is currently unavailable.',
          risk_score: 0,
          model: 'LSTM + Autoencoder',
          model_accuracy: null,
          model_auc: null,
          last_trained: null
        }),
        fetchJsonOrDefault(`/api/ai/anomalies/${apiId}?hours=24`, []),
        fetchJsonOrDefault(`/api/ai/insights/${apiId}`, []),
        fetchJsonOrDefault(`/api/ai/insights/history/${apiId}`, []),
        fetchJsonOrDefault(`/api/ai/training_runs/latest/${apiId}`, null),
        fetchJsonOrDefault(`/api/ai/training_runs/${apiId}?limit=5`, [])
      ]);

      // Build HTML
      let html = '';

      // Calculate next training time based on last training
      const trainingIntervalMinutes = 20; // AI trains every 20 minutes
      let minutesRemaining = trainingIntervalMinutes;

      // If prediction has last_trained timestamp, calculate actual remaining time
      if (prediction.last_trained) {
        const lastTrainedTime = new Date(prediction.last_trained);
        const nextTrainTime = new Date(lastTrainedTime.getTime() + trainingIntervalMinutes * 60 * 1000);
        const now = new Date();
        const msRemaining = nextTrainTime - now;
        minutesRemaining = Math.max(0, Math.floor(msRemaining / 1000 / 60));
        const secondsRemaining = Math.max(0, Math.floor((msRemaining / 1000) % 60));

        html += `
          <div class="next-training-card">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
              <i class="ri-time-line" style="font-size: 1.5rem; color: #58A6FF;"></i>
              <div>
                <div style="font-weight: 600; font-size: 1rem;">Next Automatic Training</div>
                <div style="color: #8B949E; font-size: 0.875rem;">Model retrains every ${trainingIntervalMinutes} minutes</div>
              </div>
            </div>
            <div id="training-countdown" style="font-size: 2rem; font-weight: 700; color: #58A6FF; text-align: center; font-family: 'Courier New', monospace;">
              ${minutesRemaining.toString().padStart(2, '0')}:${secondsRemaining.toString().padStart(2, '0')}
            </div>
            <div style="text-align: center; color: #8B949E; font-size: 0.875rem; margin-top: 0.5rem;">
              ${minutesRemaining === 0 && secondsRemaining === 0 ? 'Training now...' : 'until next training'}
            </div>
          </div>
        `;
      } else {
        // No last training time, show default
        html += `
          <div class="next-training-card">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
              <i class="ri-time-line" style="font-size: 1.5rem; color: #58A6FF;"></i>
              <div>
                <div style="font-weight: 600; font-size: 1rem;">Next Automatic Training</div>
                <div style="color: #8B949E; font-size: 0.875rem;">Model retrains every ${trainingIntervalMinutes} minutes</div>
              </div>
            </div>
            <div id="training-countdown" style="font-size: 2rem; font-weight: 700; color: #58A6FF; text-align: center; font-family: 'Courier New', monospace;">
              ${trainingIntervalMinutes}:00
            </div>
            <div style="text-align: center; color: #8B949E; font-size: 0.875rem; margin-top: 0.5rem;">
              until next training
            </div>
          </div>
        `;
      }

      const insightHistoryList = Array.isArray(insightHistory) ? insightHistory : [];
      const trainingHistoryList = Array.isArray(trainingRuns) ? trainingRuns : [];
      const latestTraining = latestRun && latestRun.api_id ? latestRun : trainingHistoryList[0] || null;

      if (latestTraining) {
        const runRiskLevel = (latestTraining.risk_level || 'unknown').toUpperCase();
        const runStatus = latestTraining.status || 'completed';
        const runDuration = latestTraining.duration_seconds ? `${latestTraining.duration_seconds.toFixed(1)}s` : 'N/A';
        const runTimestamp = latestTraining.completed_at || latestTraining.started_at;
        const runTimeLabel = runTimestamp ? new Date(runTimestamp).toLocaleString() : 'N/A';
        const runSampleSize = latestTraining.sample_size || latestTraining.metrics?.sample_size || 'N/A';
        const runFailure = typeof latestTraining.failure_probability === 'number'
          ? `${(latestTraining.failure_probability * 100).toFixed(1)}%`
          : 'N/A';
        const runConfidence = typeof latestTraining.confidence === 'number'
          ? `${(latestTraining.confidence * 100).toFixed(1)}%`
          : 'N/A';

        html += `
          <div class="training-run-card">
            <div class="training-run-header">
              <div>
                <div class="training-run-title"><i class="ri-history-line"></i> Latest Training Run</div>
                <div class="training-run-subtitle">${escapeHtml(runTimeLabel)}</div>
              </div>
              <div class="training-run-meta">
                <span class="training-run-status ${runStatus}">${escapeHtml(runStatus)}</span>
                <span class="training-run-badge">${escapeHtml(runRiskLevel)}</span>
              </div>
            </div>
            <div class="training-run-metrics">
              <div>
                <small>Failure Prob.</small>
                <strong>${escapeHtml(runFailure)}</strong>
              </div>
              <div>
                <small>Confidence</small>
                <strong>${escapeHtml(runConfidence)}</strong>
              </div>
              <div>
                <small>Duration</small>
                <strong>${escapeHtml(runDuration)}</strong>
              </div>
              <div>
                <small>Sample Size</small>
                <strong>${escapeHtml(String(runSampleSize))}</strong>
              </div>
            </div>
            ${latestTraining.summary ? `<p class="training-run-summary">${escapeHtml(latestTraining.summary)}</p>` : ''}
            ${latestTraining.actions && latestTraining.actions.length
            ? `<div class="training-run-actions">
                   ${latestTraining.actions.map(action => `<span>${escapeHtml(action)}</span>`).join('')} 
                 </div>`
            : ''}
          </div>
        `;
      }

      // Previous training runs
      if (trainingHistoryList.length > 1) {
        html += `
          <div class="training-history-card">
            <div class="training-history-title"><i class="ri-time-line"></i> Previous Training Runs</div>
            <ul class="training-history-list">
        `;

        trainingHistoryList.slice(1, 6).forEach(item => {
          const createdAt = item.created_at ? new Date(item.created_at).toLocaleString() : '';
          const level = item.risk_level ? item.risk_level.toUpperCase() : 'UNKNOWN';
          const score = typeof item.risk_score === 'number' ? item.risk_score : '';
          const summary = item.summary || '';
          html += `
            <li class="training-history-item">
              <div class="training-history-header">
                <span class="training-history-time">${escapeHtml(createdAt)}</span>
                <span class="training-history-badge">${escapeHtml(level)}${score !== '' ? ` · ${score}/100` : ''}</span>
              </div>
              <div class="training-history-summary">${escapeHtml(summary)}</div>
            </li>
          `;
        });

        html += `
            </ul>
          </div>
        `;
      }

      // Prediction Card
      const riskLevel = prediction.risk_score > 70 ? 'danger' : prediction.risk_score > 40 ? 'warning' : 'safe';
      const riskText = prediction.will_fail ? '<i class="ri-alert-line"></i> High Risk' : prediction.risk_score > 40 ? '<i class="ri-flashlight-line"></i> Moderate Risk' : '<i class="ri-checkbox-circle-line"></i> Low Risk';

      html += `
        <div class="ai-prediction-card">
          <div class="prediction-header">
            <div class="prediction-title">Failure Prediction</div>
            <div class="prediction-badge ${riskLevel}">${riskText}</div>
          </div>
          <div class="risk-meter">
            <div class="risk-bar">
              <div class="risk-fill" style="width: ${prediction.risk_score}%"></div>
            </div>
            <div class="risk-label">
              <span>Risk Score</span>
              <span><strong>${prediction.risk_score}/100</strong></span>
            </div>
          </div>
          <div class="prediction-details">
            <div style="margin-bottom: 0.5rem;"><strong>Confidence:</strong> ${(prediction.confidence * 100).toFixed(0)}%</div>
            <div><strong>Analysis:</strong> ${escapeHtml(prediction.reason)}</div>
          </div>
        </div>
      `;

      // Model Status Card
      const modelName = prediction.model || 'LSTM + Autoencoder';
      const modelAccuracyText = typeof prediction.model_accuracy === 'number'
        ? `${(prediction.model_accuracy * 100).toFixed(1)}%`
        : 'N/A';
      const modelAucText = typeof prediction.model_auc === 'number'
        ? prediction.model_auc.toFixed(3)
        : 'N/A';
      const lastTrainedText = prediction.last_trained
        ? new Date(prediction.last_trained).toLocaleString()
        : 'Not available';

      html += `
        <div class="ai-model-card">
          <div class="ai-model-card-header">
            <div>
              <div class="ai-model-title"><i class="ri-brain-line"></i> Current Training Model</div>
              <div class="ai-model-subtitle">${escapeHtml(modelName)}</div>
            </div>
            <div class="ai-model-meta">
              <span><strong>Last Trained:</strong> ${escapeHtml(lastTrainedText)}</span>
            </div>
          </div>
          <div class="ai-model-metrics">
            <div class="ai-model-metric">
              <small>Model Accuracy</small>
              <strong>${escapeHtml(modelAccuracyText)}</strong>
            </div>
            <div class="ai-model-metric">
              <small>Validation AUC</small>
              <strong>${escapeHtml(modelAucText)}</strong>
            </div>
            <div class="ai-model-metric">
              <small>Risk Score</small>
              <strong>${prediction.risk_score}/100</strong>
            </div>
          </div>
        </div>
      `;

      // Insights Cards
      if (insights && insights.length > 0) {
        insights.forEach(insight => {
          html += `
            <div class="insight-card ${insight.type}">
              <div class="insight-title">${insight.title}</div>
              <div class="insight-message">${escapeHtml(insight.message)}</div>
              ${insight.details ? `<div class="insight-message">${escapeHtml(insight.details)}</div>` : ''}
              ${insight.action ? `<div class="insight-action"><i class="ri-lightbulb-line"></i> ${escapeHtml(insight.action)}</div>` : ''}
            </div>
          `;
        });
      }

      // Previous AI insights history
      if (insightHistoryList.length > 1) {
        html += `
          <div class="insight-history-card">
            <div class="insight-title"><i class="ri-time-line"></i> Previous AI Insights</div>
            <ul class="insight-history-list">
        `;

        insightHistoryList.slice(1, 6).forEach(item => {
          const createdAt = item.created_at ? new Date(item.created_at).toLocaleString() : '';
          const level = item.risk_level ? item.risk_level.toUpperCase() : 'UNKNOWN';
          const score = typeof item.risk_score === 'number' ? item.risk_score : '';
          const summary = item.summary || '';
          html += `
            <li class="insight-history-item">
              <div class="insight-history-header">
                <span class="insight-history-time">${escapeHtml(createdAt)}</span>
                <span class="insight-history-badge">${escapeHtml(level)}${score !== '' ? ` · ${score}/100` : ''}</span>
              </div>
              <div class="insight-history-summary">${escapeHtml(summary)}</div>
            </li>
          `;
        });

        html += `
            </ul>
          </div>
        `;
      }

      // Anomalies
      if (anomalies && anomalies.length > 0) {
        html += `
          <div class="insight-card error">
            <div class="insight-title"><i class="ri-alert-line"></i> Anomalies Detected (${anomalies.length})</div>
            <div class="anomaly-list">
        `;
        anomalies.slice(0, 5).forEach(anomaly => {
          html += `
            <div class="anomaly-item ${anomaly.severity}">
              <strong>${anomaly.type.replace('_', ' ').toUpperCase()}:</strong> ${escapeHtml(anomaly.description)}
            </div>
          `;
        });
        html += `</div></div>`;
      }

      // If no insights or anomalies
      if (insights.length === 0 && anomalies.length === 0 && !prediction.will_fail) {
        html += `
          <div class="insight-card info">
            <div class="insight-title"><i class="ri-checkbox-circle-line"></i> All Systems Normal</div>
            <div class="insight-message">No issues detected. API is performing well.</div>
          </div>
        `;
      }

      aiInsightsContent.innerHTML = html;

      // Re-enable the AI Prediction button after results are shown
      if (aiButton) {
        aiButton.disabled = false;
        aiButton.style.opacity = '1';
        aiButton.style.cursor = 'pointer';
      }

      // Start countdown timer with actual remaining time
      if (prediction.last_trained) {
        const lastTrainedTime = new Date(prediction.last_trained);
        const nextTrainTime = new Date(lastTrainedTime.getTime() + trainingIntervalMinutes * 60 * 1000);
        startTrainingCountdown(nextTrainTime);
      } else {
        startTrainingCountdown(new Date(Date.now() + trainingIntervalMinutes * 60 * 1000));
      }

    } catch (error) {
      console.error('Error loading AI insights:', error);
      aiInsightsContent.innerHTML = '<p class="placeholder error">Failed to load AI insights</p>';
    }
  }

  // Countdown timer function - takes target time
  function startTrainingCountdown(targetTime) {
    const countdownEl = document.getElementById('training-countdown');
    if (!countdownEl) return;

    const updateTimer = () => {
      const now = new Date();
      const msRemaining = targetTime - now;

      if (msRemaining <= 0) {
        countdownEl.textContent = '00:00';
        countdownEl.style.color = '#3FB950';
        countdownEl.parentElement.querySelector('div:last-child').textContent = 'Training now...';
        return;
      }

      const totalSeconds = Math.floor(msRemaining / 1000);
      const mins = Math.floor(totalSeconds / 60);
      const secs = totalSeconds % 60;
      countdownEl.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;

      setTimeout(updateTimer, 1000);
    };

    updateTimer();
  }

  // Add AI button to monitor cards (we'll call this when rendering monitors)
  window.loadAIInsights = loadAIInsights;

  // Create GitHub Alert for downtime
  async function createGitHubAlert(apiId) {
    if (!confirm('Create a GitHub issue for this API downtime?')) {
      return;
    }

    try {
      const response = await fetch('/api/github/create-downtime-alert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_id: apiId })
      });

      // Check if response is JSON
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const text = await response.text();
        console.error('Non-JSON response:', text);
        throw new Error('Server returned an error. Check console for details.');
      }

      const result = await response.json();

      if (result.success) {
        alert(`GitHub Issue Created!\n\nIssue #${result.issue_number}\n\nView at: ${result.issue_url}`);
      } else {
        alert(`Error: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('GitHub alert error:', error);
      alert(`Error creating GitHub alert: ${error.message}`);
    }
  }

  window.createGitHubAlert = createGitHubAlert;

  // Store active timer intervals
  const activeTimers = {};

  // Prevent duplicate fetchMonitors calls
  let fetchMonitorsTimeout = null;
  const debouncedFetchMonitors = () => {
    if (fetchMonitorsTimeout) {
      clearTimeout(fetchMonitorsTimeout);
    }
    fetchMonitorsTimeout = setTimeout(() => {
      fetchMonitors();
      fetchMonitorsTimeout = null;
    }, 3000); // Wait 3 seconds before reloading
  };

  // Load training timer for an API
  function loadTrainingTimer(apiId, lastAiTraining) {
    const timerEl = document.getElementById(`timer-${apiId}`);
    if (!timerEl) return;

    // Clear existing timer if any
    if (activeTimers[apiId]) {
      clearInterval(activeTimers[apiId]);
      delete activeTimers[apiId];
    }

    const trainingIntervalMinutes = 20;

    if (lastAiTraining) {
      const lastTrainedTime = new Date(lastAiTraining);

      // Validate date
      if (isNaN(lastTrainedTime.getTime())) {
        console.error(`[Timer] Invalid date for API ${apiId}:`, lastAiTraining);
        timerEl.textContent = `${trainingIntervalMinutes}:00`;
        timerEl.style.color = '#8B949E';
        return;
      }

      const nextTrainTime = new Date(lastTrainedTime.getTime() + trainingIntervalMinutes * 60 * 1000);

      // Start countdown for this specific timer using setInterval
      const updateTimer = () => {
        const now = new Date();
        const msRemaining = nextTrainTime - now;

        if (msRemaining <= 0) {
          timerEl.textContent = '00:00';
          timerEl.style.color = '#3FB950';

          // Clear interval
          if (activeTimers[apiId]) {
            clearInterval(activeTimers[apiId]);
            delete activeTimers[apiId];
          }

          // Auto-trigger FULL training when timer reaches 00:00
          console.log(`[Timer] Auto-training (FULL) triggered for API ${apiId}`);
          fetch('/api/ai/train', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              api_id: apiId,
              force_retrain: true
            })
          }).then(response => {
            if (response.ok) {
              console.log(`[Timer] Auto-training (FULL) submitted for API ${apiId}`);
              // Use debounced reload to prevent multiple simultaneous reloads
              debouncedFetchMonitors();
            }
          }).catch(error => {
            console.error(`[Timer] Auto-training failed for API ${apiId}:`, error);
          });

          return;
        }

        const totalSeconds = Math.floor(msRemaining / 1000);
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        timerEl.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      };

      // Initial update
      updateTimer();

      // Set interval and store it
      activeTimers[apiId] = setInterval(updateTimer, 1000);
    } else {
      // No training history - just show default time
      console.log(`[Timer] No training history for API ${apiId}, showing default time`);
      timerEl.textContent = `${trainingIntervalMinutes}:00`;
      timerEl.style.color = '#8B949E';
    }
  }

  // Load alert status for an API
  async function loadAlertStatus(apiId) {
    const statusDiv = document.getElementById(`alert-status-${apiId}`);
    if (!statusDiv) return;

    try {
      const response = await fetch(`/api/alert-status/${apiId}`);
      if (!response.ok) {
        statusDiv.innerHTML = '<div style="color: #58A6FF;"><i class="ri-brain-line"></i> AI monitoring active</div>';
        return;
      }

      const data = await response.json();
      let html = '';

      if (data.downtime_alert) {
        const alert = data.downtime_alert;
        html += `<div style="color: #EF4444; margin-bottom: 0.25rem;">
          <i class="ri-alarm-warning-line"></i> Downtime alert ${getTimeAgo(alert.created_at)}
          ${alert.github_issue_url ? `<a href="${alert.github_issue_url}" target="_blank" style="color: #58A6FF;">#${alert.github_issue_number}</a>` : ''}
        </div>`;
      }

      if (data.ai_prediction) {
        const pred = data.ai_prediction;
        const probability = (Number(pred.failure_probability || 0) * 100).toFixed(0);
        const timeAgo = getTimeAgo(pred.last_check);
        const highRisk = Number(probability) >= 70;

        html += `<div style="color: ${highRisk ? '#EF4444' : '#16A34A'}; margin-bottom: 0.25rem;">
          <i class="ri-brain-line"></i> AI risk ${probability}% (${timeAgo})
          ${pred.github_issue_url ? `<a href="${pred.github_issue_url}" target="_blank" style="color: #58A6FF;">#${pred.github_issue_number}</a>` : ''}
        </div>`;
      }

      if (data.burn_rate_alert) {
        const burn = data.burn_rate_alert;
        const sev = (burn.severity || 'warning').toLowerCase();
        const color = sev === 'critical' ? '#EF4444' : '#F59E0B';
        html += `<div style="color: ${color}; margin-bottom: 0.25rem;">
          <i class="ri-fire-line"></i> Burn-rate ${sev.toUpperCase()} (1h ${burn.burn_rate_1h || 0}x, 6h ${burn.burn_rate_6h || 0}x)
        </div>`;
      }

      if (data.incident_status && data.incident_status.status === 'open') {
        const inc = data.incident_status;
        html += `<div style="color: #8B949E;">
          <i class="ri-stack-line"></i> Incident grouped: ${inc.failure_events || 0} failures, ${inc.suppressed_alerts || 0} suppressed
        </div>`;
      }

      if (!html) {
        html = '<div style="color: #58A6FF;"><i class="ri-brain-line"></i> AI monitoring active</div>';
      }

      statusDiv.innerHTML = html;
    } catch (error) {
      statusDiv.innerHTML = '<div style="color: #58A6FF;"><i class="ri-brain-line"></i> AI monitoring active</div>';
    }
  }

  // Helper function to get time ago
  function getTimeAgo(timestamp) {
    if (!timestamp) return 'recently';

    const now = new Date();
    let then;

    // Handle different timestamp formats
    if (typeof timestamp === 'string') {
      if (timestamp.includes('Z') || timestamp.includes('+')) {
        // ISO string with timezone
        then = new Date(timestamp);
      } else {
        // Assume UTC if no timezone
        then = new Date(timestamp + 'Z');
      }
    } else if (typeof timestamp === 'number') {
      // Unix timestamp
      then = new Date(timestamp);
    } else if (timestamp instanceof Date) {
      // Already a Date object
      then = timestamp;
    } else {
      // Unknown format
      return 'recently';
    }

    const diffMs = now - then;
    const diffMins = Math.floor(diffMs / 60000);

    // Handle negative time (future timestamps due to timezone issues)
    if (diffMins < 0) return 'just now';

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  }

  window.loadAlertStatus = loadAlertStatus;

  // Create incident
  createIncidentBtn.addEventListener('click', async () => {
    const title = document.getElementById('incidentTitle').value.trim();
    const summary = document.getElementById('incidentSummary').value.trim();
    const severity = document.getElementById('incidentSeverity').value;
    const rootCause = document.getElementById('incidentRootCause').value.trim();
    const fix = document.getElementById('incidentFix').value.trim();

    if (!title || !summary) {
      alert('Please fill in title and summary');
      return;
    }

    createIncidentBtn.disabled = true;

    try {
      const response = await fetch('/api/incidents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          summary,
          severity,
          root_cause: rootCause,
          fix_applied: fix,
          start_time: new Date().toISOString(),
          created_by: 'Dashboard User'
        })
      });

      if (response.ok) {
        alert('Incident created successfully!');
        document.getElementById('incidentTitle').value = '';
        document.getElementById('incidentSummary').value = '';
        document.getElementById('incidentRootCause').value = '';
        document.getElementById('incidentFix').value = '';
        loadDataSummary();
      } else {
        throw new Error('Failed to create incident');
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      createIncidentBtn.disabled = false;
    }
  });

  // --- Utility Functions ---
  const formatLatency = (ms) =>
    ms === null || ms === undefined ? "N/A" : `${ms.toFixed(2)} ms`;

  const formatPercent = (value) =>
    value === null || value === undefined || Number.isNaN(Number(value))
      ? "N/A"
      : `${Number(value).toFixed(2)}%`;

  async function loadAuthStatus() {
    if (!authBtn) return;
    try {
      const response = await fetch('/auth/me');
      if (!response.ok) return;
      const data = await response.json();
      if (data.authenticated) {
        currentSubscription = {
          plan: data.user?.subscription_plan || 'free',
          features: data.user?.subscription_features || {},
        };
        authBtn.innerHTML = '<i class="ri-logout-box-r-line" aria-hidden="true"></i> Sign Out';
        authBtn.href = '#';
        authBtn.onclick = async (event) => {
          event.preventDefault();
          await fetch('/auth/logout', { method: 'POST' });
          window.location.href = '/auth';
        };
      } else {
        currentSubscription = {
          plan: 'free',
          features: {
            premium_frequency_locked: true,
            community_communication_enabled: false
          }
        };
        authBtn.innerHTML = '<i class="ri-shield-user-line" aria-hidden="true"></i> Sign In';
        authBtn.href = '/auth';
        authBtn.onclick = null;
      }
      applySubscriptionUI();
    } catch (error) {
      currentSubscription = {
        plan: 'free',
        features: {
          premium_frequency_locked: true,
          community_communication_enabled: false
        }
      };
      authBtn.href = '/auth';
      authBtn.onclick = null;
      applySubscriptionUI();
    }
  }

  async function loadSloSummary() {
    if (!sloTotalMonitors || !sloAvgUptime || !sloAvgBudget || !sloBurnAlerts) return;
    try {
      const response = await fetch('/api/advanced/slo_summary');
      if (!response.ok) throw new Error(`SLO summary status: ${response.status}`);
      const summary = await response.json();
      const warning = Number(summary.warning_burn_rate || 0);
      const critical = Number(summary.critical_burn_rate || 0);
      sloTotalMonitors.textContent = String(summary.total_monitors ?? 0);
      sloAvgUptime.textContent = formatPercent(summary.avg_uptime_pct_24h);
      sloAvgBudget.textContent = formatPercent(summary.avg_error_budget_remaining_pct);
      sloBurnAlerts.innerHTML = `${critical} critical, ${warning} warning`;
    } catch (error) {
      sloTotalMonitors.textContent = 'N/A';
      sloAvgUptime.textContent = 'N/A';
      sloAvgBudget.textContent = 'N/A';
      sloBurnAlerts.textContent = 'N/A';
    }
  }

  function renderBurnBadge(level) {
    const safe = (level || 'none').toLowerCase();
    const icon = safe === 'critical' ? 'ri-fire-fill' : 'ri-fire-line';
    return `<span class="burn-badge ${safe}"><i class="${icon}"></i> ${safe.toUpperCase()}</span>`;
  }

  // --- Core Functions ---
  async function fetchMonitors() {
    monitorListDiv.innerHTML = '<p class="placeholder">Loading monitors...</p>';
    try {
      // Add a cache-busting parameter to ensure fresh data
      const response = await fetch(
        `/api/advanced/monitors?_=${new Date().getTime()}`
      );
      // Robust check to prevent JSON parsing errors on 404/500 responses
      if (!response.ok) {
        throw new Error(`Server responded with status: ${response.status}`);
      }
      const monitors = await response.json();
      latestMonitors = monitors;
      updateTestSelect(monitors);
      renderMonitorList(monitors);
      loadSloSummary();
      loadAuthStatus();
    } catch (error) {
      console.error("Fetch Monitors Error:", error);
      monitorListDiv.innerHTML =
        '<p class="placeholder error">Failed to load monitors. Check server connection and API routes.</p>';
    }
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    const editId = apiEditId.value;
    const payload = {
      url: document.getElementById("apiUrl").value,
      category: document.getElementById("apiCategory").value,
      header_name: document.getElementById("apiHeaderName").value,
      header_value: document.getElementById("apiHeaderValue").value,
      check_frequency_minutes: Number(document.getElementById("apiFrequency").value),
      notification_email: document.getElementById("apiEmail").value,
    };
    const url = editId
      ? "/api/advanced/update_monitor"
      : "/api/advanced/add_monitor";
    // MongoDB uses string IDs, don't parse as integer
    if (editId) payload.id = editId;

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || "Failed to save monitor.");
      }
      closeModal();
      fetchMonitors();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  }

  async function deleteMonitor(apiId) {
    if (!confirm('Are you sure you want to delete this monitor?')) {
      return;
    }

    try {
      const response = await fetch('/api/advanced/delete_monitor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: apiId })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || 'Failed to delete monitor.');
      }

      fetchMonitors();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  }

  // Make deleteMonitor available globally
  window.deleteMonitor = deleteMonitor;

  // --- Render Functions ---
  function renderMonitorList(monitors) {
    if (!monitors || monitors.length === 0) {
      monitorListDiv.innerHTML =
        '<p class="placeholder">No APIs are being monitored. Add one to get started!</p>';
      return;
    }
    // Group by category
    const categorized = monitors.reduce((acc, m) => {
      const category = m.category || "Uncategorized";
      if (!acc[category]) acc[category] = [];
      acc[category].push(m);
      return acc;
    }, {});

    // Sort categories, putting "Uncategorized" last
    const sortedCategories = Object.keys(categorized).sort((a, b) => {
      if (a === 'Uncategorized') return 1;
      if (b === 'Uncategorized') return -1;
      return a.localeCompare(b);
    });

    monitorListDiv.innerHTML = sortedCategories.map(category => `
          <div class="category-group">
              <h3>${category}</h3>
              <div class="monitor-list">
                  ${categorized[category].map(renderMonitorItem).join('')}
              </div>
          </div>
      `).join('');

    // Load alert status and training timer for each monitor
    monitors.forEach(monitor => {
      loadAlertStatus(monitor.id);
      loadTrainingTimer(monitor.id, monitor.last_ai_training);
    });
  }

  function getStatusMeta(statusValue) {
    const rawStatus = (statusValue || "Pending").toString().trim();
    const normalized = rawStatus
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");

    if (normalized === "network-down" || normalized === "low-network") {
      return { label: "Low Network", className: "status-low-network" };
    }

    return {
      label: rawStatus || "Pending",
      className: `status-${normalized || "pending"}`
    };
  }

  function renderMonitorItem(monitor) {
    const statusMeta = getStatusMeta(monitor.last_status);
    const uptime = Number(monitor.uptime_pct_24h || 0);
    const latency = Number(monitor.avg_latency_24h || 0);
    const p95Latency = Number(monitor.p95_latency_24h || 0);
    const budgetRemaining = Number(monitor.error_budget_remaining_pct || 0);
    const burnLevel = (monitor.burn_rate_alert_level || "none").toLowerCase();
    const rootCauseHint = (monitor.last_root_cause_hint || "unknown").toUpperCase();

    const sparklineHtml = (monitor.recent_checks || []).map(check => {
      const barClass = check.is_up ? 'sparkline-bar-up' : 'sparkline-bar-down';
      const tooltipText = `${check.is_up ? 'Up' : 'Down'} at ${new Date(check.timestamp).toLocaleString()}`;
      return `<div class="${barClass}" style="height: 100%;" data-tooltip="${tooltipText}"></div>`;
    }).join('');

    return `
          <div class="monitor-item" data-id="${monitor.id}">
              <div class="monitor-info">
                  <div class="monitor-url-container">
                    <span class="status-indicator ${statusMeta.className}"></span>
                    <strong class="monitor-url">${monitor.url}</strong>
                  </div>
                  <div class="monitor-meta-tags">
                    <span class="monitor-category"><i class="ri-folder-line"></i> ${monitor.category || 'Uncategorized'}</span>
                    <div id="training-timer-${monitor.id}" class="training-timer-inline">
                        <i class="ri-brain-line"></i>
                        <span id="timer-${monitor.id}" class="timer-value">--:--</span>
                    </div>
                  </div>
              </div>
              
              <div class="monitor-stats-grid">
                  <div class="stat-group">
                    <div class="stat-item">
                        <small><i class="ri-heart-pulse-line"></i> Uptime</small>
                        <strong class="${uptime > 99 ? 'status-up-text' : 'status-warn-text'}">${uptime.toFixed(2)}%</strong>
                    </div>
                    <div class="stat-item">
                        <small><i class="ri-speed-line"></i> Latency</small>
                        <strong>${latency.toFixed(0)}<span class="unit">ms</span></strong>
                    </div>
                  </div>
                  <div class="sparkline-wrapper">
                    <div class="sparkline-container" title="Last 15 checks">${sparklineHtml.length > 0 ? sparklineHtml : '<div class="sparkline-empty">No data</div>'}</div>
                    <div class="root-cause-tag">${rootCauseHint}</div>
                  </div>
              </div>

              <div class="monitor-actions-container">
                  <div class="status-badge-container">
                    <span class="status-label ${statusMeta.className}">${statusMeta.label}</span>
                    ${burnLevel !== 'none' ? renderBurnBadge(burnLevel) : ''}
                  </div>
                  <div class="action-buttons">
                    <button class="button-ai-insights" onclick="event.stopPropagation(); loadAIInsights('${monitor.id}')" title="AI Prediction">
                      <i class="ri-magic-line"></i> <span>AI Analyze</span>
                    </button>
                    <button class="button-icon-small" onclick="event.stopPropagation(); showTrainingHistory('${monitor.id}')" title="Training History">
                      <i class="ri-history-line"></i>
                    </button>
                  </div>
                  <div id="alert-status-${monitor.id}" class="auto-alert-status">
                      <i class="ri-brain-line"></i> AI Active
                  </div>
              </div>
          </div>
      `;
  }

  async function showDetailsView(apiId) {
    mainView.classList.add("hidden");
    detailsView.classList.remove("hidden");
    detailsView.innerHTML = '<p class="placeholder">Loading details...</p>';

    try {
      const [monitorRes, historyRes] = await Promise.all([
        fetch(`/api/advanced/monitors?_=${new Date().getTime()}`).then((res) =>
          res.json()
        ),
        fetch(`/api/advanced/history?id=${apiId}`).then((res) => res.json()),
      ]);
      // MongoDB returns string IDs, so compare as strings
      const monitor = monitorRes.find((m) => m.id === apiId || m.id === String(apiId));

      if (!monitor) {
        throw new Error(`Monitor with ID ${apiId} not found`);
      }

      renderDetails(
        monitor,
        historyRes.history,
        historyRes.total_pages,
        historyRes.current_page
      );
    } catch (error) {
      console.error("Error showing details view:", error);
      detailsView.innerHTML =
        '<p class="placeholder error">Failed to load details.</p>';
    }
  }

  function renderDetails(monitor, history, totalPages, currentPage) {
    const latest = history[0] || {};
    const statusMeta = getStatusMeta(monitor.last_status);
    const uptime24h = Number(monitor.uptime_pct_24h || 0);
    const p95 = Number(monitor.p95_latency_24h || 0);
    const errorBudget = Number(monitor.error_budget_remaining_pct || 0);
    const burn1h = Number(monitor.burn_rate_1h || 0);
    const burn6h = Number(monitor.burn_rate_6h || 0);
    const burnLevel = (monitor.burn_rate_alert_level || "none").toUpperCase();
    const rootCauseHint = (monitor.last_root_cause_hint || latest.root_cause_hint || "unknown").toUpperCase();
    const rootCauseDetails = monitor.last_root_cause_details || latest.root_cause_details || "Not available";
    let certCardHtml = "<p>N/A (Not an HTTPS site or check failed)</p>";
    if (latest.tls_cert_subject) {
      const expiresDate = new Date(latest.tls_cert_valid_until);
      const isExpired = expiresDate < new Date();
      certCardHtml = `
        <div class="cert-details">
            <p><strong>Subject:</strong> ${latest.tls_cert_subject}</p>
            <p><strong>Issuer:</strong> ${latest.tls_cert_issuer}</p>
            <p><strong>Expiry:</strong> <span class="${isExpired ? "status-down" : ""
        }">${expiresDate.toLocaleDateString()}</span></p>
        </div>`;
    }

    detailsView.innerHTML = `
        <header class="details-header">
            <div class="details-header-info">
                <button id="backBtn" class="button-secondary"><i class="ri-arrow-left-line"></i> Back to List</button>
                <h2>${monitor.url}</h2>
                <div class="details-meta">
                   <span><i class="ri-link"></i> ${latest.url_type || "N/A"}</span>
                   <span><i class="ri-folder-line"></i> ${monitor.category || "Uncategorized"}</span>
                </div>
            </div>
            <div class="header-actions">
                <button class="button-secondary edit-btn" data-id="${monitor.id
      }">Edit</button>
                <button class="button-secondary delete-btn" data-id="${monitor.id
      }">Delete</button>
            </div>
        </header>
        <div class="details-grid">
            <div class="metric-card"><h4>Current Status</h4><p class="${statusMeta.className}">${statusMeta.label}</p></div>
            <div class="metric-card"><h4>Avg. Latency (24h)</h4><p>${formatLatency(
        monitor.avg_latency_24h
      )}</p></div>
            <div class="metric-card"><h4>P95 Latency (24h)</h4><p>${formatLatency(
        p95
      )}</p></div>
            <div class="metric-card"><h4>Uptime (24h)</h4><p>${uptime24h.toFixed(
        2
      )} %</p></div>
            <div class="metric-card"><h4>Error Budget Remaining</h4><p>${errorBudget.toFixed(2)}%</p></div>
            <div class="metric-card"><h4>Burn Rate</h4><p>${burn1h.toFixed(2)}x (1h) / ${burn6h.toFixed(2)}x (6h) <span class="burn-badge ${burnLevel.toLowerCase()}">${burnLevel}</span></p></div>
            <div class="metric-card"><h4>Root-Cause Hint</h4><p>${rootCauseHint}</p><small>${rootCauseDetails}</small></div>
            <div class="metric-card large-card">
                <h4>Certificate</h4>
                ${certCardHtml}
            </div>
        </div>
        <h3>Latency History</h3>
        <div class="chart-container-large"><canvas id="detailLatencyChart"></canvas></div>
        <h3>Check History</h3>
        <table class="history-log-table">
            <thead><tr><th>Timestamp</th><th>Status</th><th>Latency</th><th>Root Cause</th><th>Details</th></tr></thead>
            <tbody id="historyLogBody"></tbody>
        </table>
        <div id="historyPagination" class="pagination-controls"></div>
    `;
    renderHistoryChart(history);
    renderHistoryTable(history);
    renderPagination(monitor.id, totalPages, currentPage);
  }

  function renderHistoryTable(history) {
    const tableBody = document.getElementById("historyLogBody");
    if (!history || history.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="5" class="placeholder">No history yet.</td></tr>';
      return;
    }
    tableBody.innerHTML = history
      .map((h) => {
        const isLowNetwork = h.check_skipped === true || h.skip_reason === "network_unavailable";
        const rowStatus = isLowNetwork ? "LOW NETWORK" : (h.status_code || "ERR");
        const indicatorClass = isLowNetwork ? "low-network" : (h.is_up ? "up" : "down");
        const rootHint = (h.root_cause_hint || (isLowNetwork ? "network" : "unknown")).toUpperCase();
        return `
            <tr>
                <td>${new Date(h.timestamp).toLocaleString()}</td>
                <td><span class="status-indicator status-${indicatorClass}"></span> ${rowStatus}</td>
                <td>${h.total_latency_ms
            ? `${h.total_latency_ms.toFixed(2)} ms`
            : "N/A"
          }</td>
                <td>${rootHint}</td>
                <td><button class="report-btn" data-log-id="${h.id
          }">View Full Report</button></td>
            </tr>
        `;
      })
      .join("");
  }

  function renderPagination(apiId, totalPages, currentPage) {
    const controls = document.getElementById("historyPagination");
    if (totalPages <= 1) {
      controls.innerHTML = "";
      return;
    }

    // Generate smart pagination with ellipsis
    let pages = [];
    const delta = 2; // Number of pages to show around current page

    for (let i = 1; i <= totalPages; i++) {
      if (
        i === 1 || // Always show first page
        i === totalPages || // Always show last page
        (i >= currentPage - delta && i <= currentPage + delta) // Show pages around current
      ) {
        pages.push(i);
      } else if (pages[pages.length - 1] !== '...') {
        pages.push('...');
      }
    }

    const buttons = pages.map(page => {
      if (page === '...') {
        return '<span class="pagination-ellipsis">...</span>';
      }
      return `<button data-page="${page}" class="${page === currentPage ? 'active' : ''}">${page}</button>`;
    }).join('');

    controls.innerHTML = `
      <button data-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''}>
        <i class="ri-arrow-left-s-line"></i> Previous
      </button>
      ${buttons}
      <button data-page="${currentPage + 1}" ${currentPage === totalPages ? 'disabled' : ''}>
        Next <i class="ri-arrow-right-s-line"></i>
      </button>
    `;

    controls
      .querySelectorAll("button[data-page]")
      .forEach((btn) =>
        btn.addEventListener("click", () =>
          fetchHistoryPage(apiId, btn.dataset.page)
        )
      );
  }

  async function fetchHistoryPage(apiId, page) {
    try {
      const response = await fetch(
        `/api/advanced/history?id=${apiId}&page=${page}`
      );
      const data = await response.json();
      renderHistoryTable(data.history);
      renderPagination(apiId, data.total_pages, data.current_page);
    } catch (error) {
      console.error("Failed to fetch history page:", error);
    }
  }

  async function showReport(logId) {
    try {
      const response = await fetch(`/api/advanced/log_details/${logId}`);
      if (!response.ok) throw new Error("Log not found.");
      const log = await response.json();

      let certHtml = `<div class="report-section"><h4><i class="ri-shield-check-line"></i> TLS Certificate</h4><p>No certificate information available (not an HTTPS URL or check failed).</p></div>`;
      if (log.tls_cert_subject) {
        certHtml = `
          <div class="report-section">
              <h4><i class="ri-shield-check-line"></i> TLS Certificate</h4>
              <div class="cert-info-grid">
                <div class="cert-info-item">
                  <i class="ri-lock-line"></i>
                  <span class="cert-label">Subject</span>
                  <span class="cert-value">${log.tls_cert_subject}</span>
                </div>
                <div class="cert-info-item">
                  <i class="ri-building-line"></i>
                  <span class="cert-label">Issuer</span>
                  <span class="cert-value">${log.tls_cert_issuer}</span>
                </div>
                <div class="cert-info-item">
                  <i class="ri-global-line"></i>
                  <span class="cert-label">SANs</span>
                  <span class="cert-value">${log.tls_cert_sans || "None"}</span>
                </div>
                <div class="cert-info-item">
                  <i class="ri-calendar-check-line"></i>
                  <span class="cert-label">Valid From</span>
                  <span class="cert-value">${new Date(log.tls_cert_valid_from).toLocaleString()}</span>
                </div>
                <div class="cert-info-item">
                  <i class="ri-calendar-event-line"></i>
                  <span class="cert-label">Valid Until</span>
                  <span class="cert-value">${new Date(log.tls_cert_valid_until).toLocaleString()}</span>
                </div>
              </div>
          </div>
        `;
      }

      document.getElementById("reportModalContent").innerHTML = `
        <button id="closeReportBtn" class="modal-close-btn"><i class="ri-close-line"></i></button>
        <div class="report-header">
          <h3><i class="ri-file-list-3-line"></i> Full Status Report</h3>
          <p class="report-meta">
            <span><i class="ri-link"></i> ${log.url_type}</span>
            <span><i class="ri-time-line"></i> ${new Date(log.timestamp).toLocaleString()}</span>
          </p>
        </div>
        
        <div class="report-grid">
            <div class="report-section">
                <h4><i class="ri-pulse-line"></i> Status</h4>
                <div class="status-box ${log.is_up ? 'status-success' : 'status-error'}">
                  <i class="ri-${log.is_up ? 'checkbox-circle' : 'close-circle'}-fill"></i>
                  <span class="status-code">${log.status_code || "ERR"}</span>
                  <span class="status-text">${log.is_up ? 'UP' : 'DOWN'}</span>
                </div>
                ${log.error_message ? `
                  <div class="error-box">
                    <i class="ri-error-warning-line"></i>
                    <span>${log.error_message}</span>
                  </div>
                ` : ''}
            </div>
            
            <div class="report-section">
                <h4><i class="ri-speed-line"></i> Latency Breakdown</h4>
                <div class="latency-grid">
                    <div class="latency-item">
                      <i class="ri-time-line"></i>
                      <span class="latency-label">Total</span>
                      <span class="latency-value">${formatLatency(log.total_latency_ms)}</span>
                    </div>
                    <div class="latency-item">
                      <i class="ri-global-line"></i>
                      <span class="latency-label">DNS</span>
                      <span class="latency-value">${formatLatency(log.dns_latency_ms)}</span>
                    </div>
                    <div class="latency-item">
                      <i class="ri-link-m"></i>
                      <span class="latency-label">TCP</span>
                      <span class="latency-value">${formatLatency(log.tcp_latency_ms)}</span>
                    </div>
                    <div class="latency-item">
                      <i class="ri-shield-check-line"></i>
                      <span class="latency-label">TLS</span>
                      <span class="latency-value">${formatLatency(log.tls_latency_ms)}</span>
                    </div>
                    <div class="latency-item">
                      <i class="ri-server-line"></i>
                      <span class="latency-label">Server</span>
                      <span class="latency-value">${formatLatency(log.server_processing_latency_ms)}</span>
                    </div>
                    <div class="latency-item">
                      <i class="ri-download-line"></i>
                      <span class="latency-label">Download</span>
                      <span class="latency-value">${formatLatency(log.content_download_latency_ms)}</span>
                    </div>
                </div>
            </div>
            
            ${certHtml}
        </div>
      `;
      reportModal.classList.remove("hidden");
      updateBodyScrollLock();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  }

  function renderHistoryChart(history) {
    const ctx = document.getElementById("detailLatencyChart").getContext("2d");
    const reversedHistory = [...history].reverse();
    const activeTheme = document.documentElement.getAttribute("data-theme") || "dark";
    const isLight = activeTheme === "light";
    const chartColors = {
      line: isLight ? "#1f6ff0" : "#58A6FF",
      fill: isLight ? "rgba(31, 111, 240, 0.12)" : "rgba(88, 166, 255, 0.1)",
      tick: isLight ? "#526789" : "#8B949E",
      grid: isLight ? "rgba(77, 105, 152, 0.22)" : "#30363D",
      tooltipBg: isLight ? "#ffffff" : "#161B22",
      tooltipText: isLight ? "#182844" : "#E6EDF3",
      pointBorder: isLight ? "#ffffff" : "#0D1117",
    };
    if (detailChart) detailChart.destroy();
    detailChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: reversedHistory.map((h) =>
          new Date(h.timestamp).toLocaleTimeString()
        ),
        datasets: [
          {
            label: "Latency (ms)",
            data: reversedHistory.map((h) => h.total_latency_ms || 0),
            borderColor: chartColors.line,
            backgroundColor: chartColors.fill,
            fill: true,
            tension: 0.4,
            pointRadius: reversedHistory.map((h) => (h.is_up ? 3 : 5)),
            pointBackgroundColor: reversedHistory.map((h) =>
              h.is_up ? "#238636" : "#DA3633"
            ),
            pointBorderColor: chartColors.pointBorder,
            pointHoverRadius: 7,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            ticks: { color: chartColors.tick, font: { weight: "600" } },
            grid: { color: chartColors.grid },
          },
          x: {
            ticks: { color: chartColors.tick, font: { weight: "600" } },
            grid: { color: chartColors.grid },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: chartColors.tooltipBg,
            titleColor: chartColors.tooltipText,
            bodyColor: chartColors.tooltipText,
            titleFont: { size: 14, weight: "bold" },
            bodyFont: { size: 12 },
            padding: 10,
            cornerRadius: 6,
          },
        },
      },
    });
  }

  // --- Modal Controls ---
  const FREQUENCY_OPTIONS = [
    "60", "30", "10", "5", "2", "1", "0.5", "0.167"
  ];

  function normalizeFrequencyValue(freq) {
    if (freq === null || freq === undefined) return "";

    // If already matches an option, return immediately
    if (FREQUENCY_OPTIONS.includes(String(freq))) {
      return String(freq);
    }

    const num = Number(freq);
    if (Number.isNaN(num)) {
      return String(freq);
    }

    // Snap to closest defined option (handles float serialization like 0.1666666667)
    let closest = FREQUENCY_OPTIONS[0];
    let minDiff = Math.abs(num - Number(closest));
    for (const option of FREQUENCY_OPTIONS.slice(1)) {
      const optionNum = Number(option);
      const diff = Math.abs(num - optionNum);
      if (diff < minDiff) {
        minDiff = diff;
        closest = option;
      }
    }

    // Only snap if difference is within tolerance (0.001 minutes ≈ 0.06s)
    if (minDiff <= 0.001) {
      return closest;
    }

    return String(num);
  }

  function openModal(monitor = null) {
    addApiForm.reset();
    if (monitor) {
      modalTitle.textContent = "Edit Monitor";
      modalSubmitBtn.textContent = "Save Changes";
      apiEditId.value = monitor.id;
      document.getElementById("apiUrl").value = monitor.url;
      document.getElementById("apiCategory").value = monitor.category || "";
      document.getElementById("apiHeaderName").value = monitor.header_name || "";
      document.getElementById("apiHeaderValue").value = monitor.header_value || "";
      document.getElementById("apiFrequency").value = normalizeFrequencyValue(monitor.check_frequency_minutes);
      document.getElementById("apiEmail").value = monitor.notification_email || "";
    } else {
      modalTitle.textContent = "Add New Monitor";
      modalSubmitBtn.textContent = "Add Monitor";
      apiEditId.value = "";
    }
    addApiModal.classList.remove("hidden");
    updateBodyScrollLock();
  }

  function closeModal() {
    addApiModal.classList.add("hidden");
    updateBodyScrollLock();
  }

  function closeReportModal() {
    reportModal.classList.add("hidden");
    updateBodyScrollLock();
  }

  // --- Event Listeners ---
  addApiBtn.addEventListener("click", () => openModal());
  cancelBtn.addEventListener("click", closeModal);
  addApiModal.addEventListener("click", (e) => e.target === addApiModal && closeModal());
  reportModal.addEventListener("click", (e) => e.target === reportModal && closeReportModal());
  addApiForm.addEventListener("submit", handleFormSubmit);

  monitorListDiv.addEventListener("click", (e) => {
    const item = e.target.closest(".monitor-item");
    if (item) {
      showDetailsView(item.dataset.id);
    }
  });

  const tooltip = document.getElementById('tooltip');

  function showTooltip(e) {
    const text = e.target.dataset.tooltip;
    if (!text) return;
    tooltip.textContent = text;
    tooltip.classList.remove('hidden');
    tooltip.classList.add('visible');
    moveTooltip(e);
  }

  function hideTooltip() {
    tooltip.classList.remove('visible');
    tooltip.classList.add('hidden');
  }

  function moveTooltip(e) {
    tooltip.style.left = `${e.clientX + 15}px`;
    tooltip.style.top = `${e.clientY + 15}px`;
  }

  monitorListDiv.addEventListener('mouseover', e => {
    if (e.target.matches('.sparkline-bar-up, .sparkline-bar-down')) {
      showTooltip(e);
    }
  });

  monitorListDiv.addEventListener('mouseout', e => {
    if (e.target.matches('.sparkline-bar-up, .sparkline-bar-down')) {
      hideTooltip();
    }
  });

  monitorListDiv.addEventListener('mousemove', e => {
    if (e.target.matches('.sparkline-bar-up, .sparkline-bar-down')) {
      moveTooltip(e);
    }
  });

  detailsView.addEventListener("click", async (e) => {
    const backBtn = e.target.closest("#backBtn");
    const editBtn = e.target.closest(".edit-btn");
    const deleteBtn = e.target.closest(".delete-btn");
    const reportBtn = e.target.closest(".report-btn");

    if (backBtn) {
      detailsView.classList.add("hidden");
      mainView.classList.remove("hidden");
      fetchMonitors();
    } else if (editBtn) {
      // MongoDB uses string IDs
      const apiId = editBtn.dataset.id;
      const res = await fetch(`/api/advanced/monitors?_=${new Date().getTime()}`);
      const monitors = await res.json();
      const monitorToEdit = monitors.find(m => m.id === apiId);
      openModal(monitorToEdit);
    } else if (deleteBtn) {
      // MongoDB uses string IDs
      const apiId = deleteBtn.dataset.id;
      if (confirm("Are you sure you want to delete this monitor? This action cannot be undone.")) {
        await fetch("/api/advanced/delete_monitor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: apiId }),
        });
        detailsView.classList.add("hidden");
        mainView.classList.remove("hidden");
        fetchMonitors();
      }
    } else if (reportBtn) {
      // Log IDs are also strings in MongoDB
      showReport(reportBtn.dataset.logId);
    }
  });

  document.body.addEventListener("click", (e) => {
    if (e.target.id === "closeReportBtn") {
      closeReportModal();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;

    if (tokenHelpModal && !tokenHelpModal.classList.contains("hidden")) {
      tokenHelpModal.classList.add("hidden");
    } else if (workerResponsesModal && !workerResponsesModal.classList.contains("hidden")) {
      workerResponsesModal.classList.add("hidden");
    } else if (alertPreviewModal && !alertPreviewModal.classList.contains("hidden")) {
      alertPreviewModal.classList.add("hidden");
    } else if (trainingHistoryModal && !trainingHistoryModal.classList.contains("hidden")) {
      trainingHistoryModal.classList.add("hidden");
    } else if (aiInsightsModal && !aiInsightsModal.classList.contains("hidden")) {
      aiInsightsModal.classList.add("hidden");
    } else if (reportModal && !reportModal.classList.contains("hidden")) {
      reportModal.classList.add("hidden");
    } else if (addApiModal && !addApiModal.classList.contains("hidden")) {
      addApiModal.classList.add("hidden");
    } else if (communityPanel && !communityPanel.classList.contains("hidden")) {
      communityPanel.classList.add("hidden");
    } else if (devDataPanel && !devDataPanel.classList.contains("hidden")) {
      devDataPanel.classList.add("hidden");
      settingsBtn?.setAttribute("aria-expanded", "false");
    }
    updateBodyScrollLock();
  });

  // --- Initial Load ---
  updateBodyScrollLock();
  fetchMonitors();

  // Auto-refresh every 1 minute (60000 ms)
  let refreshCount = 0;
  setInterval(() => {
    refreshCount++;
    console.log(`[Auto-refresh #${refreshCount}] Updating monitor status...`);
    fetchMonitors();
  }, 60000);

  // Show last refresh time in console
  console.log('[Auto-refresh] Enabled - Updates every 60 seconds');
});
