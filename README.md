# 🤖 Proactive AI Co-Pilot for Predictive API Monitoring

An AI-powered system that predicts API failures, provides root cause analysis, and gives developer insights by correlating API performance with GitHub commits, pull requests, and issues.

## 🌟 Features

### 🔮 AI-Powered Predictions
- **Failure Prediction**: Machine learning models predict API failures before they happen
- **Risk Scoring**: 0-100 risk assessment for each monitored API
- **Anomaly Detection**: Real-time detection of unusual patterns in API behavior
- **Pattern Recognition**: Identifies recurring issues and trends

### 📊 Advanced Monitoring
- **Real-time API Monitoring**: Continuous health checks with configurable intervals
- **Latency Tracking**: DNS, TCP, TLS, server processing, and download time breakdown
- **Uptime Metrics**: 24-hour uptime percentage tracking
- **TLS Certificate Monitoring**: Expiry alerts and security checks

### 🔗 GitHub Integration
- **Commit Synchronization**: Automatically syncs repository commits
- **Pull Request Tracking**: Monitors PR activity and correlates with API performance
- **Issue Management**: Syncs and tracks GitHub issues
- **Data Correlation**: Links API failures to code changes

### 🎨 Modern Dashboard
- **Dark/Light Theme**: Toggle between themes
- **Interactive Charts**: Real-time latency and performance graphs
- **Category Organization**: Group APIs by category
- **AI Insights Modal**: Detailed predictions and recommendations

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **Database**: MongoDB
- **AI/ML**: TensorFlow, scikit-learn, NumPy
- **Frontend**: HTML5, CSS3, JavaScript, Chart.js
- **APIs**: GitHub REST API, PyCURL for HTTP monitoring

## 📦 Installation

### Prerequisites
- Python 3.8+
- MongoDB 4.0+
- Git

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/YOUR_USERNAME/ai-copilot-api-monitoring.git
cd ai-copilot-api-monitoring
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env and add your GitHub token and MongoDB URI
```

4. **Start MongoDB**
```bash
# Windows
net start MongoDB

# Linux/Mac
sudo systemctl start mongod
```

5. **Run the application**
```bash
python src/app.py
```

6. **Access the dashboard**
- Simple Dashboard: http://localhost:5000
- Advanced Dashboard: http://localhost:5000/advanced_monitor

## 🚀 Quick Start

### Start the Application
```bash
START_HERE.bat  # Windows
# or
python src/app.py
```

### Run Tests
```bash
python -m pytest tests/
```

### Start Test API (for testing)
```bash
cd "running API"
python api_testing.py
```

## 📖 Documentation

📚 **Project Documentation**

Quick Links:
- **[Project Overview](docs/PROJECT_OVERVIEW.md)** - Complete system documentation
- **[Project Handbook](docs/PROJECT_HANDBOOK.md)** - Operations, alerting, and troubleshooting

## 🎯 Usage

### Add an API to Monitor
1. Click "Add API" button
2. Enter API URL and configuration
3. Set check frequency and notification email
4. Click "Save"

### Sync GitHub Data
1. Click the settings icon (⚙️)
2. Enter repository owner and name
3. Set sync period (days)
4. Click "Sync GitHub Data"

### View AI Insights
1. Click "🤖 AI Insights" on any monitored API
2. View failure predictions and risk scores
3. Check anomalies and recommendations

### Create Incident Report
1. Open settings panel
2. Fill in incident details
3. Add root cause and fix applied
4. Click "Create Incident"

## 🧠 AI Models

### Random Forest Classifier
- Predicts API failure probability
- Features: latency, status codes, error patterns
- Accuracy: ~85-90%

### LSTM Neural Network
- Time-series prediction for latency trends
- Detects gradual degradation
- Forecasts future performance

### Anomaly Detection
- Statistical analysis of API behavior
- Identifies outliers and unusual patterns
- Real-time alerting

## 📊 MongoDB Collections

- `monitored_apis` - API configurations
- `monitoring_logs` - Check results and history
- `git_commits` - Synced GitHub commits
- `issues` - GitHub issues
- `incident_reports` - Incident tracking
- `application_logs` - Error logs
- `data_correlations` - Links between data

## 🔧 Configuration

### Environment Variables (.env)
```env
GITHUB_TOKEN=your_github_personal_access_token
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=api_monitoring

# Optional alerting providers
WHATSAPP_API_URL=https://api.example.com/whatsapp/send
WHATSAPP_API_TOKEN=your_whatsapp_api_token_here

# Twilio (preferred SMS provider)
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_MESSAGING_SERVICE_SID=your_twilio_messaging_service_sid_here

# Generic SMS fallback (only used if Twilio is not configured)
SMS_API_URL=https://api.example.com/sms/send
SMS_API_TOKEN=your_generic_sms_api_token_here

# IVR provider
IVR_API_URL=https://api.example.com/ivr/call
IVR_API_TOKEN=your_ivr_api_token_here

# Translation provider (optional)
TRANSLATION_API_URL=https://translation.googleapis.com/language/translate/v2
TRANSLATION_API_KEY=your_translation_api_key_here
```

### API Monitoring Settings
- Check frequency: 1-60 minutes
- Notification email: Optional
- Custom headers: Optional

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_ai.py

# Run with coverage
python -m pytest --cov=. tests/
```

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

- Your Name - Initial work

## 🙏 Acknowledgments

- GitHub API for repository data
- MongoDB for flexible data storage
- TensorFlow and scikit-learn for ML capabilities
- Chart.js for beautiful visualizations

## 📧 Contact

- GitHub: [@YOUR_USERNAME](https://github.com/YOUR_USERNAME)
- Email: your.email@example.com

## 🔗 Links

- [Documentation](docs/)
- [Issue Tracker](https://github.com/YOUR_USERNAME/ai-copilot-api-monitoring/issues)
- [Project Board](https://github.com/YOUR_USERNAME/ai-copilot-api-monitoring/projects)

## 🧠 AI Training History & Insights

- **Detailed Persistence:** Training sessions are stored in the `ai_training_runs` MongoDB collection alongside their risk scores, confidence, risk components, summary, actions, and log snippets to provide an audit trail of every retrain (forced or scheduled).
- **Dedicated Endpoints:** The backend exposes `POST /api/ai/training_runs` for ingestion, `GET /api/ai/training_runs/<api_id>` for history, and `GET /api/ai/training_runs/latest/<api_id>` for quick access to the freshest run, enabling the UI to stay in sync with stored runs.
- **UI Experience:** Each monitor card now includes both the “🧠 AI Prediction” modal (showing the current prediction, insights, anomalies, and countdown) and a “Training History” button that opens a themed modal highlighting the latest trained model, metrics, risk factors, recommended actions, and log excerpts before listing prior runs.
- **LLM-Style Summaries:** Predictions and training runs surface LLM-like explanations, anomaly recommendations, confidence/risk narratives, and suggested actions, ensuring the insights feel contextual and human-readable.

---

**Made with ❤️ for better API monitoring**
