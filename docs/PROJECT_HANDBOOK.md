# 📘 Project Handbook — API Downtime Monitoring & AI Alerting

This handbook consolidates every operational detail from the previous documentation set into a single reference.
Use it alongside **`PROJECT_OVERVIEW.md`** for high-level context.

---

## 1. Core Capabilities

| Area | Highlights |
|------|------------|
| API Monitoring | Polls every 30 seconds, records latency/status, supports REST/GraphQL/WebSocket/DB endpoints. |
| Dual Alerting | • **Immediate**: downtime/recovery GitHub issues.<br>• **Predictive**: AI model forecasts (>40% risk) with rich context. |
| AI Engine | Category-aware LSTM + Autoencoder, retrains on demand or every 20 minutes, cached models per category. |
| GitHub Automation | Issues include labels, risk level, recommended actions; auto-closes on recovery. |
| Dashboard | `/advanced_monitor` with live tiles, trend charts, alert history, AI insights modal. |
| Analytics Layer | Correlates incidents with commits, displays anomaly explanations, confidence, and risk factors. |

---

## 2. Environment & Startup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
2. **Ensure MongoDB is running** (default URI `mongodb://localhost:27017/`).
3. **Start services (two terminals)**
   ```bash
   # Terminal 1 — AI Training Service
   cd "d:\Users\Desktop\The Project\API Downtime"
   python src\ai_training_service.py

   # Terminal 2 — Main App
   cd "d:\Users\Desktop\The Project\API Downtime"
   python src\app.py
   ```
4. **Confirm health**
   ```bash
   curl http://localhost:5001/health   # AI service should report "running"
   curl http://localhost:5000/health   # Main app should report "healthy"
   ```
5. **Open dashboard** → `http://localhost:5000/advanced_monitor`

**Important:** keep both terminals active. The AI modal depends on the training service (port 5001).

---

## 3. Operating the Dashboard

- **Adding/Editing APIs:** Use the configuration table; each record stores polling interval, category, and auth info.
- **Live Tiles:** Color-coded status with latency, uptime %, error counts, and the “🧠 AI Prediction” button.
- **Historical Charts:** Latency & uptime trends (Chart.js) auto-refresh every 60 s.
- **Alert Feed:** Shows downtime, recovery, and AI prediction alerts with timestamps and GitHub links.
- **AI Insights Modal:** 
  - Launch via **🧠 AI Prediction**.
  - Displays staged progress (“Preparing dataset → Training LSTM → Training Autoencoder → Finalizing”).
  - Waits for true training completion before fetching results.
  - Shows failure probability, confidence, risk level, anomalies, and recommended actions.

---

## 4. AI Training & Predictions

### 4.1 Training Flow
1. Frontend posts to `/api/ai/train` (main app).
2. Main app forwards to `POST /train/full` on the AI service (port 5001).
3. `ai_training_service.py` streams progress via callbacks:
   - `starting` → environment prep
   - `preparing_data`
   - `lstm_epoch x/y`
   - `autoencoder_epoch x/y`
   - `analyzing` → generating predictions
   - `completed`
4. Minimum UI display time is 5 s; actual completion time typically 40–80 s (force retrain clears caches).

### 4.2 Models
- **LSTM Classifier** per category (sequence length = 48, features include uptime, latency, error rate, status codes).
- **Autoencoder** trained on healthy sequences for anomaly scoring.
- **Confidence Calculation** blends model agreement, data quality, and calibrated probability; realistic range 50–95%.
- **Artifacts** stored under `models/<category>/` with scaler, LSTM, autoencoder, and metadata.

### 4.3 Forcing Retrains & Troubleshooting
- Use UI button or API with `{ "force_retrain": true }` to discard cached weights.
- If training ends in <5 s, delete stale models:
  ```bash
  del /Q models\*.h5
  del /Q models\*.pkl
  ```
- Watch AI service logs for epoch counts, early stopping, and anomaly thresholds.

---

## 5. Alerting System

| Alert Type | Trigger | GitHub Labels | Notes |
|------------|---------|---------------|-------|
| **Downtime** | 3 consecutive failures | `api-downtime`, status-dependent labels | Opens issue, auto-closes when 3 successes observed. |
| **Recovery** | 3 consecutive successes post-downtime | adds comment + closes issue | Includes uptime summary. |
| **AI Predictive** | Failure probability ≥ 0.40 | `ai-prediction`, `high-risk`/`medium-risk` | Issue body lists risk factors, confidence, recommended actions. |

Alert history persisted in MongoDB (`alert_history`). Duplicate predictive alerts suppressed while one is open.

---

## 6. GitHub Integration

1. **Token**: Fine-grained PAT with `repo` scope; store in settings UI or `.env`.
2. **Repository Target**: Configurable per API or global default.
3. **Issue Templates**: Auto-generated with:
   - API details (URL, category)
   - Risk level & probability
   - Confidence & risk score
   - Top anomalies / factors
   - Recommended action checklist
   - Timestamp and training duration
4. **Sync Jobs**: Background sync updates issue status and correlates commits that touch failing endpoints.

Troubleshooting:
- Verify token permissions.
- Inspect `github_sync.log` for rate limits or auth failures.
- Use the guidelines in this handbook; legacy GitHub docs have been merged here.

---

## 7. Data & Persistence

- **MongoDB Collections**
  - `monitored_apis`: API metadata, category, credentials, `last_ai_training` timestamp.
  - `api_status_history`: Time-series metrics.
  - `alert_history`: Alert events, GitHub issue link, status.
  - `ai_predictions`: Stored prediction outputs for auditing.
- **Model Cache**: `CategoryAwareAIPredictor.category_models` keeps loaded models in-memory; cleared on force retrain.
- **Training Logs**: AI service prints durations, epochs, accuracy, AUC, anomaly threshold.

---

## 8. Common Tasks & Commands

| Task | Command / Action |
|------|------------------|
| Start both services | See §2.3 |
| Trigger AI training (CLI) | `curl -X POST http://localhost:5000/api/ai/train -H "Content-Type: application/json" -d "{\"api_id\":\"<id>\",\"force_retrain\":true}"` |
| Poll training status | `curl http://localhost:5001/training/status/<api_id>` |
| Fetch latest prediction | `curl http://localhost:5000/api/ai/predict/<api_id>` |
| Remove cached models | `del /Q models\*.h5` & `del /Q models\*.pkl` |
| View dashboard | `http://localhost:5000/advanced_monitor` |

---

## 9. Troubleshooting Reference

1. **Browser console shows “Training service unavailable”**
   - Ensure AI service terminal is running; retry POST.
2. **Status stuck on “idle”**
   - Training service probably not receiving request; check firewall/port.
3. **Progress bar stuck <100%**
   - Inspect `/training/status/<api_id>` for errors; look at AI service logs.
4. **Confidence always 100%**
   - Delete cached model files and retrain with fresh data.
5. **GitHub issues missing**
   - PAT scope/repo mismatch; test with curl using same token.
6. **MongoDB connectivity errors**
   - Verify `MONGODB_URI`; MongoDB must allow connections from both services.

---

## 10. File Map (Key Code Modules)

| Path | Purpose |
|------|---------|
| `src/app.py` | Flask main app, API routes, GitHub hooks. |
| `src/ai_training_service.py` | Dedicated training server, progress callbacks. |
| `src/ai_predictor.py` | Category-aware predictor, model training & inference. |
| `static_advanced/monitor.js` | Advanced dashboard logic, AI modal, polling. |
| `templates/advanced_monitor.html` | Dashboard layout. |
| `models/` | Persisted TensorFlow models & scalers per category. |
| `logs/` | Runtime logs and GitHub sync logs. |

---

## 11. Maintenance Checklist

- [ ] Keep requirements up to date; re-run `pip install -r requirements.txt` after dependency changes.
- [ ] Monitor disk usage of `models/` and `api_status_history` collections.
- [ ] Rotate GitHub PATs before expiry.
- [ ] Periodically validate AI predictions against real incidents for calibration.
- [ ] Back up MongoDB data (mongodump) periodically.

---

Everything from the old documentation set has been consolidated here. Refer to this handbook for day-to-day operations, setup, alerting, AI training, and troubleshooting guidance.
