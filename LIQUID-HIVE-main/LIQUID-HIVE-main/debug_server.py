#!/usr/bin/env python3
"""
Debug script to diagnose LIQUID-HIVE server initialization issues
"""
import sys
import os
import traceback

def test_imports():
    """Test all the imports that the server uses"""
    print("Testing imports...")
    
    try:
        from capsule_brain.observability.metrics import MetricsMiddleware, router as metrics_router
        print("✓ Metrics imports successful")
    except Exception as e:
        print(f"✗ Metrics imports failed: {e}")
    
    try:
        from capsule_brain.planner.plan import plan_once
        print("✓ Planner imports successful")
    except Exception as e:
        print(f"✗ Planner imports failed: {e}")
    
    try:
        from capsule_brain.core.capsule_engine import CapsuleEngine
        print("✓ CapsuleEngine import successful")
    except Exception as e:
        print(f"✗ CapsuleEngine import failed: {e}")
    
    try:
        from capsule_brain.core.intent_modeler import IntentModeler
        print("✓ IntentModeler import successful")
    except Exception as e:
        print(f"✗ IntentModeler import failed: {e}")

    try:
        from hivemind.config import Settings
        print("✓ Settings import successful")
    except Exception as e:
        print(f"✗ Settings import failed: {e}")

    try:
        from hivemind.roles_text import TextRoles
        print("✓ TextRoles import successful")
    except Exception as e:
        print(f"✗ TextRoles import failed: {e}")

    try:
        from hivemind.judge import Judge
        print("✓ Judge import successful")
    except Exception as e:
        print(f"✗ Judge import failed: {e}")

    try:
        from hivemind.policies import decide_policy
        print("✓ Policies import successful")
    except Exception as e:
        print(f"✗ Policies import failed: {e}")

    try:
        from hivemind.strategy_selector import StrategySelector
        print("✓ StrategySelector import successful")
    except Exception as e:
        print(f"✗ StrategySelector import failed: {e}")

    try:
        from hivemind.rag.retriever import Retriever
        print("✓ Retriever import successful")
    except Exception as e:
        print(f"✗ Retriever import failed: {e}")

    try:
        from hivemind.rag.citations import format_context
        print("✓ Citations import successful")
    except Exception as e:
        print(f"✗ Citations import failed: {e}")

    try:
        from hivemind.clients.vllm_client import VLLMClient
        print("✓ VLLMClient import successful")
    except Exception as e:
        print(f"✗ VLLMClient import failed: {e}")

    try:
        from hivemind.clients.vl_client import VLClient
        print("✓ VLClient import successful")  
    except Exception as e:
        print(f"✗ VLClient import failed: {e}")

    try:
        from hivemind.roles_vl import VisionRoles
        print("✓ VisionRoles import successful")
    except Exception as e:
        print(f"✗ VisionRoles import failed: {e}")

    try:
        from hivemind.resource_estimator import ResourceEstimator
        print("✓ ResourceEstimator import successful")
    except Exception as e:
        print(f"✗ ResourceEstimator import failed: {e}")

    try:
        from hivemind.adapter_deployment_manager import AdapterDeploymentManager
        print("✓ AdapterDeploymentManager import successful")
    except Exception as e:
        print(f"✗ AdapterDeploymentManager import failed: {e}")

    try:
        from hivemind.tool_auditor import ToolAuditor
        print("✓ ToolAuditor import successful")
    except Exception as e:
        print(f"✗ ToolAuditor import failed: {e}")

    try:
        from hivemind.confidence_modeler import ConfidenceModeler, TrustPolicy
        print("✓ ConfidenceModeler import successful")
    except Exception as e:
        print(f"✗ ConfidenceModeler import failed: {e}")

    try:
        from hivemind.autonomy.curiosity import CuriosityEngine
        print("✓ CuriosityEngine import successful")
    except Exception as e:
        print(f"✗ CuriosityEngine import failed: {e}")

    try:
        import redis
        print("✓ Redis import successful")
    except Exception as e:
        print(f"✗ Redis import failed: {e}")

def test_settings():
    """Test settings initialization"""
    print("\nTesting settings initialization...")
    try:
        from hivemind.config import Settings
        settings = Settings()
        print("✓ Settings instance created")
        
        print(f"  vllm_endpoint: {getattr(settings, 'vllm_endpoint', 'Not set')}")
        print(f"  redis_url: {getattr(settings, 'redis_url', 'Not set')}")
        print(f"  foundational_adapter_path: {getattr(settings, 'foundational_adapter_path', 'Not set')}")
        print(f"  runs_dir: {getattr(settings, 'runs_dir', 'Not set')}")
        print(f"  rag_index: {getattr(settings, 'rag_index', 'Not set')}")
        
        return settings
    except Exception as e:
        print(f"✗ Settings initialization failed: {e}")
        traceback.print_exc()
        return None

def test_capsule_engine():
    """Test CapsuleEngine initialization"""
    print("\nTesting CapsuleEngine initialization...")
    try:
        from capsule_brain.core.capsule_engine import CapsuleEngine
        engine = CapsuleEngine()
        print("✓ CapsuleEngine instance created")
        return engine
    except Exception as e:
        print(f"✗ CapsuleEngine initialization failed: {e}")
        traceback.print_exc()
        return None

def test_directories():
    """Test if required directories exist"""
    print("\nChecking required directories...")
    dirs_to_check = [
        "/app/runs",
        "/app/rag_index", 
        "/app/adapters",
        "/app/adapters/foundational/champion_v1",
        "./runs",
        "./rag_index",
        "./adapters",
        "./adapters/foundational/champion_v1"
    ]
    
    for dir_path in dirs_to_check:
        if os.path.exists(dir_path):
            print(f"✓ {dir_path} exists")
        else:
            print(f"✗ {dir_path} missing")

def main():
    print("LIQUID-HIVE System Diagnostic")
    print("=" * 50)
    
    test_imports()
    settings = test_settings()
    engine = test_capsule_engine()
    test_directories()
    
    print("\n" + "=" * 50)
    print("Diagnostic Summary:")
    print(f"Settings initialized: {'✓' if settings else '✗'}")
    print(f"CapsuleEngine initialized: {'✓' if engine else '✗'}")
    
    if settings and engine:
        print("\n✓ Basic components are working!")
        print("The issue might be in the startup exception handling or missing external services.")
    else:
        print("\n✗ Core component initialization failed.")
        print("Check the errors above for specific issues.")

if __name__ == "__main__":
    main()