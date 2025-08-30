#!/usr/bin/env python3
"""
E2E Test for Unified Runtime CPU Fallback Router and RAG Watcher Hardening
"""

import requests
import sys
import json
import subprocess
import time
import os
import pathlib
import asyncio
from datetime import datetime

class UnifiedRuntimeTester:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                if data:
                    response = requests.post(url, json=data, headers=headers, params=params)
                else:
                    response = requests.post(url, headers=headers, params=params)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"Response: {response.text}")

            return success, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_healthz(self):
        """Test health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/healthz",
            200
        )
        if success:
            print(f"Health response: {response}")
            return response.get('ok', False)
        return False

    def test_providers(self):
        """Test providers endpoint"""
        success, response = self.run_test(
            "Providers Status",
            "GET", 
            "api/providers",
            200
        )
        if success:
            print(f"Providers response: {response}")
            return response
        return {}

    def test_chat(self, query="hello router"):
        """Test chat endpoint"""
        success, response = self.run_test(
            "Chat Generation",
            "POST",
            "api/chat",
            200,
            params={"q": query}
        )
        if success:
            print(f"Chat response keys: {list(response.keys())}")
            if 'provider' in response:
                print(f"Provider used: {response['provider']}")
            return response
        return {}

    def test_pytest_suite(self):
        """Run pytest test suite"""
        print(f"\n🔍 Running pytest test suite...")
        try:
            result = subprocess.run([
                "pytest", "-q", 
                "tests/test_rag_watcher_resilience.py",
                "tests/test_router_fallback.py", 
                "tests/test_providers_endpoint.py"
            ], capture_output=True, text=True, cwd="/app")
            
            if result.returncode == 0:
                print("✅ Pytest suite passed")
                self.tests_passed += 1
            else:
                print("❌ Pytest suite failed")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
            
            self.tests_run += 1
            return result.returncode == 0
        except Exception as e:
            print(f"❌ Failed to run pytest: {str(e)}")
            self.tests_run += 1
            return False

def main():
    print("🚀 Starting Unified Runtime E2E Tests")
    print("=" * 50)
    
    # Setup
    tester = UnifiedRuntimeTester()
    
    # Test 1: Health check
    health_ok = tester.test_healthz()
    if not health_ok:
        print("❌ Health check failed, stopping tests")
        return 1

    # Test 2: Providers status
    providers_status = tester.test_providers()
    if not providers_status:
        print("❌ Providers endpoint failed, stopping tests")
        return 1

    # Verify expected provider configuration
    expected_providers = {"vllm": False, "openai": False, "hf_cpu": True}
    actual_providers = providers_status.get("providers", {})
    
    print(f"\nProvider Status Verification:")
    for provider, expected in expected_providers.items():
        actual = actual_providers.get(provider, False)
        status = "✅" if actual == expected else "❌"
        print(f"{status} {provider}: expected={expected}, actual={actual}")

    # Test 3: Chat functionality
    chat_response = tester.test_chat("hello router")
    if not chat_response:
        print("❌ Chat endpoint failed")
        return 1

    # Verify provider is included in response
    if 'provider' not in chat_response:
        print("❌ Chat response missing provider field")
        return 1
    
    if chat_response['provider'] != 'hf_cpu':
        print(f"❌ Expected provider 'hf_cpu', got '{chat_response['provider']}'")
        return 1

    # Test 4: Run pytest suite
    pytest_passed = tester.test_pytest_suite()
    if not pytest_passed:
        print("❌ Pytest suite failed")
        return 1

    # Test 5: Check API logs for structured logging
    print(f"\n🔍 Checking API logs for structured logging...")
    try:
        with open("/tmp/api.log", "r") as f:
            log_content = f.read()
            if "unified_runtime.providers.hf_cpu_provider" in log_content and "generation" in log_content:
                print("✅ Found structured log with provider key")
                tester.tests_passed += 1
            else:
                print("❌ Structured log with provider key not found")
            tester.tests_run += 1
    except Exception as e:
        print(f"❌ Failed to check logs: {str(e)}")
        tester.tests_run += 1

    # Print results
    print(f"\n📊 Test Results:")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())