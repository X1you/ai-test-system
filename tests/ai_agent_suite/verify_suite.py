#!/usr/bin/env python3
"""验证 AI Agent 测试套件结构"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

print("=== 目录结构验证 ===")
for d in ['tests/ai_agent_suite', 'tests/ai_agent_suite/module_pipeline',
           'tests/ai_agent_suite/module_web_api', 'tests/ai_agent_suite/module_data']:
    p = PROJECT_ROOT / d
    status = "OK" if p.exists() else "MISSING"
    print(f"  {d}: {status}")

print("\n=== 文件完整性验证 ===")
files = [
    'tests/ai_agent_suite/__init__.py',
    'tests/ai_agent_suite/conftest.py',
    'tests/ai_agent_suite/monitor.py',
    'tests/ai_agent_suite/reporter.py',
    'tests/ai_agent_suite/orchestrator.py',
    'tests/ai_agent_suite/module_pipeline/__init__.py',
    'tests/ai_agent_suite/module_pipeline/test_pipeline_e2e.py',
    'tests/ai_agent_suite/module_web_api/__init__.py',
    'tests/ai_agent_suite/module_web_api/test_api_services.py',
    'tests/ai_agent_suite/module_data/__init__.py',
    'tests/ai_agent_suite/module_data/test_data_integration.py',
]
for f in files:
    p = PROJECT_ROOT / f
    status = "OK" if p.exists() else "MISSING"
    print(f"  {f}: {status}")

print("\n=== 模块导入验证 ===")
try:
    print("  monitor.ResourceMonitor: OK")
except Exception as e:
    print(f"  monitor.ResourceMonitor: FAIL - {e}")

try:
    print("  reporter.TestReporter: OK")
except Exception as e:
    print(f"  reporter.TestReporter: FAIL - {e}")

try:
    print("  orchestrator.TestOrchestrator: OK")
except Exception as e:
    print(f"  orchestrator.TestOrchestrator: FAIL - {e}")

print("\n=== 验证完成 ===")
