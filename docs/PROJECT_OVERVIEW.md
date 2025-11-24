# 🚀 API Downtime Monitoring & Intelligent Alerting System

## Overview

A comprehensive API monitoring system with AI-powered predictive analytics and automatic GitHub issue creation.

## Core Features

### 1. Real-Time API Monitoring
- Monitor multiple APIs (every 30 seconds)
- Track uptime, latency, response codes
- Support for REST, GraphQL, WebSocket, Databases

### 2. Dual Alert System

**System 1: Immediate Downtime/Recovery**
- Detects downtime (3 consecutive failures)
- Creates GitHub issue automatically
- Closes issue on recovery (3 consecutive successes)

**System 2: AI Predictive Alerts**
- Trains every 15 minutes
- Predicts failures (>70% risk)
- Creates warning GitHub issues
- LSTM + Autoencoder neural networks

### 3. GitHub Integration
- Automatic issue creation
- Auto-close on recovery
- Labels: `api-downtime`, `ai-prediction`, `automated`

### 4. Developer Correlation
- Links downtime to commits
- Identifies code changes
- Root cause analysis

### 5. Advanced Dashboard
- Real-time status
- Auto-refresh (60 seconds)
- Alert indicators
- AI prediction display
- Historical charts

## Technology Stack

- **Backend:** Python Flask
- **Database:** MongoDB
- **Frontend:** JavaScript, Chart.js
- **AI/ML:** TensorFlow, Keras
- **Integration:** GitHub API

## Architecture

```
Flask App → MongoDB → Alert Manager → GitHub Issues
    ↓
AI Predictor → Model Training → Predictions
    ↓
Dashboard → Auto-refresh → Live Status
```

## Zero Manual Work

Everything is automatic:
- ✅ Monitors APIs continuously
- ✅ Detects downtime automatically
- ✅ Creates GitHub issues automatically
- ✅ Trains AI models automatically
- ✅ Closes issues on recovery automatically

## Quick Start

1. Install: `pip install -r requirements.txt`
2. Start MongoDB: `mongod`
3. Run: `START_HERE.bat`
4. Open: `http://localhost:5000/advanced_monitor`
5. Configure GitHub in Settings panel

## Key Benefits

- 🔍 Proactive monitoring
- 🤖 AI-powered predictions
- 🚨 Automatic alerting
- 📊 Complete visibility
- 👨‍💻 Developer correlation
