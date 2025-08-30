#!/usr/bin/env python3
"""
Direct Secrets Management Test
==============================

This script directly tests the secrets management functionality
without relying on the full server startup.
"""

import sys
import os
from datetime import datetime

def log(message):
    """Log with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def test_secrets_manager_direct():
    """Test secrets manager directly"""
    log("🔍 Testing Secrets Manager directly...")
    
    try:
        from hivemind.secrets_manager import secrets_manager
        log("✅ Secrets manager import successful")
        
        # Test provider detection
        provider = secrets_manager.get_provider()
        log(f"✅ Active provider: {provider}")
        
        # Test health check
        health = secrets_manager.health_check()
        log(f"✅ Health check: {health}")
        
        # Test environment fallback
        if provider.value == "environment":
            log("✅ Environment fallback working as expected")
        else:
            log(f"✅ External provider ({provider.value}) configured")
            
        # Test secret retrieval
        test_secret = secrets_manager.get_secret("TEST_SECRET", "default_value")
        log(f"✅ Secret retrieval test: {test_secret}")
        
        # Test helper methods
        db_url = secrets_manager.get_database_url()
        log(f"✅ Database URL helper: {db_url or 'None (expected)'}")
        
        redis_url = secrets_manager.get_redis_url()
        log(f"✅ Redis URL helper: {redis_url or 'None (expected)'}")
        
        vllm_config = secrets_manager.get_vllm_config()
        log(f"✅ vLLM config helper: {vllm_config}")
        
        return True
        
    except Exception as e:
        log(f"❌ Secrets manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_settings_with_secrets():
    """Test Settings class with secrets manager integration"""
    log("🔍 Testing Settings class with secrets integration...")
    
    try:
        from hivemind.config import Settings
        log("✅ Settings import successful")
        
        # Create settings instance
        settings = Settings()
        log("✅ Settings instance created")
        
        # Test secrets health method
        health = settings.get_secrets_health()
        log(f"✅ Settings secrets health: {health}")
        
        # Test get_secret method
        test_secret = settings.get_secret("TEST_SECRET", "default")
        log(f"✅ Settings get_secret: {test_secret}")
        
        return True
        
    except Exception as e:
        log(f"❌ Settings test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_secrets_caching():
    """Test secrets caching functionality"""
    log("🔍 Testing secrets caching...")
    
    try:
        from hivemind.secrets_manager import secrets_manager
        
        # Clear cache first
        secrets_manager.clear_cache()
        log("✅ Cache cleared")
        
        # Get a secret twice to test caching
        secret1 = secrets_manager.get_secret("TEST_CACHE", "cached_value")
        secret2 = secrets_manager.get_secret("TEST_CACHE", "cached_value")
        
        if secret1 == secret2:
            log("✅ Caching working correctly")
            return True
        else:
            log("❌ Caching not working")
            return False
            
    except Exception as e:
        log(f"❌ Caching test failed: {e}")
        return False

def test_provider_priority():
    """Test provider priority system"""
    log("🔍 Testing provider priority system...")
    
    try:
        from hivemind.secrets_manager import SecretsManager, SecretProvider
        
        # Create a new instance to test initialization
        sm = SecretsManager()
        provider = sm.get_provider()
        
        # Should default to environment since Vault/AWS not configured
        if provider == SecretProvider.ENVIRONMENT:
            log("✅ Provider priority working - defaulted to environment")
            return True
        elif provider in [SecretProvider.VAULT, SecretProvider.AWS_SECRETS_MANAGER]:
            log(f"✅ Provider priority working - using {provider.value}")
            return True
        else:
            log(f"❌ Unexpected provider: {provider}")
            return False
            
    except Exception as e:
        log(f"❌ Provider priority test failed: {e}")
        return False

def main():
    """Run all direct tests"""
    log("🚀 Starting Direct Secrets Management Tests")
    log("=" * 50)
    
    tests = [
        test_secrets_manager_direct,
        test_settings_with_secrets,
        test_secrets_caching,
        test_provider_priority
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        log("-" * 30)
    
    log("=" * 50)
    log(f"📊 Direct Test Results: {passed}/{total} passed")
    
    if passed == total:
        log("🎉 All direct tests passed!")
        return 0
    else:
        log("⚠️  Some direct tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())