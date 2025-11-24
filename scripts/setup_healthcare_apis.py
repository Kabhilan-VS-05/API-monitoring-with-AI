#!/usr/bin/env python3
"""
Setup Healthcare APIs for Community Guardian
Creates sample healthcare API monitors for demonstration
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from pymongo import MongoClient
from datetime import datetime, timedelta
import json

def setup_healthcare_apis():
    """Create sample healthcare API monitors"""
    
    # Connect to MongoDB
    try:
        client = MongoClient('mongodb://localhost:27017/')
        db = client['api_monitoring']
        monitored_apis = db['monitored_apis']
        
        # Clear existing data
        monitored_apis.delete_many({})
        
        # Sample healthcare APIs
        healthcare_apis = [
            {
                "name": "City Ambulance Dispatch System",
                "url": "https://api.emergency.gov/ambulance/status",
                "category": "emergency_dispatch",
                "priority": "critical",
                "impact_score": 95,
                "contact": "dispatch@city.gov",
                "fallback_url": "https://backup.emergency.gov/ambulance/status",
                "check_interval": 30,
                "status": "up",
                "last_check": datetime.utcnow(),
                "uptime_percentage": 99.5,
                "response_time_ms": 120,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Hospital ICU Bed Availability",
                "url": "https://api.health.gov/hospital/icu-beds",
                "category": "life_support",
                "priority": "critical", 
                "impact_score": 98,
                "contact": "icu@generalhospital.gov",
                "fallback_url": "https://backup.health.gov/hospital/icu-beds",
                "check_interval": 15,
                "status": "up",
                "last_check": datetime.utcnow(),
                "uptime_percentage": 98.2,
                "response_time_ms": 95,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Emergency Alert Broadcasting",
                "url": "https://api.emergency.gov/alerts/broadcast",
                "category": "emergency_alerts",
                "priority": "critical",
                "impact_score": 92,
                "contact": "alerts@emergency.gov",
                "fallback_url": "https://backup.emergency.gov/alerts/broadcast",
                "check_interval": 20,
                "status": "up",
                "last_check": datetime.utcnow(),
                "uptime_percentage": 97.8,
                "response_time_ms": 85,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Telemedicine Video Consultation",
                "url": "https://api.telehealth.gov/consultations/video",
                "category": "telemedicine",
                "priority": "high",
                "impact_score": 75,
                "contact": "support@telehealth.gov",
                "fallback_url": "https://backup.telehealth.gov/consultations/video",
                "check_interval": 45,
                "status": "up",
                "last_check": datetime.utcnow(),
                "uptime_percentage": 96.5,
                "response_time_ms": 150,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Vaccination Appointment Booking",
                "url": "https://api.health.gov/vaccination/appointments",
                "category": "vaccination",
                "priority": "high",
                "impact_score": 70,
                "contact": "vaccine@health.gov",
                "fallback_url": "https://backup.health.gov/vaccination/appointments",
                "check_interval": 60,
                "status": "up",
                "last_check": datetime.utcnow(),
                "uptime_percentage": 94.2,
                "response_time_ms": 200,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Hospital Bed Availability System",
                "url": "https://api.health.gov/hospital/beds",
                "category": "hospital_operations",
                "priority": "high",
                "impact_score": 80,
                "contact": "beds@generalhospital.gov",
                "fallback_url": "https://backup.health.gov/hospital/beds",
                "check_interval": 30,
                "status": "up",
                "last_check": datetime.utcnow(),
                "uptime_percentage": 95.8,
                "response_time_ms": 110,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Electronic Health Records Access",
                "url": "https://api.health.gov/records/patient",
                "category": "health_records",
                "priority": "medium",
                "impact_score": 60,
                "contact": "records@health.gov",
                "fallback_url": "https://backup.health.gov/records/patient",
                "check_interval": 90,
                "status": "up",
                "last_check": datetime.utcnow(),
                "uptime_percentage": 93.5,
                "response_time_ms": 180,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Medical Supply Chain Tracking",
                "url": "https://api.health.gov/supply/medical",
                "category": "supply_chain",
                "priority": "medium",
                "impact_score": 55,
                "contact": "supply@health.gov",
                "fallback_url": "https://backup.health.gov/supply/medical",
                "check_interval": 120,
                "status": "up",
                "last_check": datetime.utcnow(),
                "uptime_percentage": 92.1,
                "response_time_ms": 220,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Public Health Disease Tracking",
                "url": "https://api.health.gov/public/diseases",
                "category": "public_health",
                "priority": "medium",
                "impact_score": 50,
                "contact": "epidemiology@health.gov",
                "fallback_url": "https://backup.health.gov/public/diseases",
                "check_interval": 180,
                "status": "up",
                "last_check": datetime.utcnow(),
                "uptime_percentage": 91.8,
                "response_time_ms": 250,
                "created_at": datetime.utcnow()
            },
            # Add some "down" APIs for demonstration
            {
                "name": "Emergency Medical Services Dispatch",
                "url": "https://api.emergency.gov/ems/dispatch",
                "category": "emergency_dispatch",
                "priority": "critical",
                "impact_score": 96,
                "contact": "ems@emergency.gov",
                "fallback_url": "https://backup.emergency.gov/ems/dispatch",
                "check_interval": 10,
                "status": "down",
                "last_check": datetime.utcnow() - timedelta(minutes=5),
                "uptime_percentage": 87.3,
                "response_time_ms": None,
                "created_at": datetime.utcnow()
            },
            {
                "name": "Rural Clinic Telemedicine",
                "url": "https://api.ruralhealth.gov/telemedicine/connect",
                "category": "telemedicine",
                "priority": "high",
                "impact_score": 72,
                "contact": "support@ruralhealth.gov",
                "fallback_url": "https://backup.ruralhealth.gov/telemedicine/connect",
                "check_interval": 60,
                "status": "down",
                "last_check": datetime.utcnow() - timedelta(minutes=12),
                "uptime_percentage": 89.1,
                "response_time_ms": None,
                "created_at": datetime.utcnow()
            }
        ]
        
        # Insert healthcare APIs
        result = monitored_apis.insert_many(healthcare_apis)
        
        print(f"✅ Created {len(result.inserted_ids)} healthcare API monitors")
        print("\n📊 Healthcare API Summary:")
        
        # Count by priority
        critical_count = len([api for api in healthcare_apis if api['priority'] == 'critical'])
        high_count = len([api for api in healthcare_apis if api['priority'] == 'high'])
        medium_count = len([api for api in healthcare_apis if api['priority'] == 'medium'])
        
        print(f"  🚨 Critical Priority: {critical_count}")
        print(f"  ⚕️ High Priority: {high_count}")
        print(f"  📋 Medium Priority: {medium_count}")
        
        # Count by status
        up_count = len([api for api in healthcare_apis if api['status'] == 'up'])
        down_count = len([api for api in healthcare_apis if api['status'] == 'down'])
        
        print(f"  ✅ APIs Up: {up_count}")
        print(f"  ❌ APIs Down: {down_count}")
        
        print("\n🏥 Healthcare Categories:")
        categories = {}
        for api in healthcare_apis:
            category = api['category']
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        for category, count in sorted(categories.items()):
            icon = {
                'emergency_dispatch': '🚨',
                'life_support': '❤️',
                'emergency_alerts': '📢',
                'hospital_operations': '🏥',
                'telemedicine': '💻',
                'vaccination': '💉',
                'health_records': '📋',
                'supply_chain': '🚚',
                'public_health': '📊'
            }.get(category, '⚕️')
            print(f"  {icon} {category.replace('_', ' ').title()}: {count}")
        
        print("\n🎯 Sample APIs created for Community Guardian demonstration!")
        print("📱 Start the application: python src/app.py")
        print("🌐 Visit: http://localhost:5000/advanced_monitor")
        
    except Exception as e:
        print(f"❌ Error setting up healthcare APIs: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🏥 Community Guardian - Healthcare API Setup")
    print("=" * 50)
    
    success = setup_healthcare_apis()
    
    if success:
        print("\n✅ Healthcare API setup completed successfully!")
    else:
        print("\n❌ Healthcare API setup failed!")
        sys.exit(1)
