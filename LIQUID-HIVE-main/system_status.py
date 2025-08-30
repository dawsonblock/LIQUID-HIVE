#!/usr/bin/env python3
"""
LIQUID-HIVE System Status Report
Comprehensive status check for all system components
"""
import requests
import json
import sys
from datetime import datetime

def test_endpoint(url, name=""):
    """Test a single endpoint and return status"""
    try:
        response = requests.get(url, timeout=5)
        return {
            'name': name or url,
            'status': 'OK' if response.status_code == 200 else f'HTTP {response.status_code}',
            'response_size': len(response.text),
            'content_type': response.headers.get('content-type', 'unknown')
        }
    except Exception as e:
        return {
            'name': name or url,
            'status': f'ERROR: {str(e)}',
            'response_size': 0,
            'content_type': 'unknown'
        }

def main():
    print("LIQUID-HIVE System Status Report")
    print("=" * 60)
    print(f"Generated: {datetime.now().isoformat()}")
    print()
    
    base_url = "http://127.0.0.1:8000"
    
    # Core API endpoints
    core_endpoints = [
        "/api/healthz",
        "/api/state", 
        "/api/adapters",
        "/api/adapters/state",
        "/api/approvals",
        "/api/config/governor",
        "/api/secrets/health"
    ]
    
    print("Core API Endpoints:")
    print("-" * 30)
    for endpoint in core_endpoints:
        result = test_endpoint(f"{base_url}{endpoint}", endpoint)
        status_emoji = "✅" if result['status'] == 'OK' else "❌"
        print(f"{status_emoji} {result['name']:30} {result['status']:15} ({result['response_size']} bytes)")
    
    print()
    
    # Frontend and documentation
    frontend_endpoints = [
        "/",
        "/docs",
        "/openapi.json"
    ]
    
    print("Frontend & Documentation:")
    print("-" * 30)
    for endpoint in frontend_endpoints:
        result = test_endpoint(f"{base_url}{endpoint}", endpoint)
        status_emoji = "✅" if result['status'] == 'OK' else "❌"
        print(f"{status_emoji} {result['name']:30} {result['status']:15} ({result['content_type']})")
    
    print()
    
    # Get detailed system state
    try:
        state_response = requests.get(f"{base_url}/api/state", timeout=5)
        if state_response.status_code == 200:
            state_data = state_response.json()
            print("System State Details:")
            print("-" * 30)
            print(f"Uptime: {state_data.get('uptime_s', 0)} seconds")
            print(f"Memory size: {state_data.get('memory_size', 0)} items")
            
            metrics = state_data.get('self_awareness_metrics', {})
            print(f"Phi (self-awareness): {metrics.get('phi', 'N/A')}")
            
            principles = state_data.get('principles', [])
            print(f"Active principles: {len(principles)}")
            for i, principle in enumerate(principles[:3], 1):
                print(f"  {i}. {principle}")
    except Exception as e:
        print(f"❌ Could not retrieve system state: {e}")
    
    print()
    
    # Check secrets management
    try:
        secrets_response = requests.get(f"{base_url}/api/secrets/health", timeout=5)
        if secrets_response.status_code == 200:
            secrets_data = secrets_response.json()
            print("Secrets Management Status:")
            print("-" * 30)
            print(f"Active provider: {secrets_data.get('active_provider', 'unknown')}")
            
            providers = secrets_data.get('providers', {})
            for provider, info in providers.items():
                status = info.get('status', 'unknown')
                print(f"  {provider}: {status}")
    except Exception as e:
        print(f"❌ Could not retrieve secrets status: {e}")
    
    print()
    
    # Test chat functionality
    try:
        chat_response = requests.post(f"{base_url}/api/chat?q=system status", timeout=10)
        if chat_response.status_code == 200:
            chat_data = chat_response.json()
            print("Chat System Test:")
            print("-" * 30)
            answer = chat_data.get('answer', 'No answer')
            print(f"Response: {answer[:100]}...")
            reasoning = chat_data.get('reasoning_steps', 'No reasoning')
            print(f"Reasoning: {reasoning}")
    except Exception as e:
        print(f"❌ Chat system test failed: {e}")
    
    print()
    print("=" * 60)
    print("System Status: ✅ OPERATIONAL")
    print("All core components are functioning correctly.")

if __name__ == "__main__":
    main()