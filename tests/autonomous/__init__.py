"""
自主测试系统 — 支持 AI 智能体独立执行 60 分钟+ 的全面自动化测试。

模块组成：
  - run_autonomous.py: 主编排器（入口）
  - test_phases.py: 8 个测试阶段，200+ 测试用例
  - test_engine.py: 测试执行框架
  - data_generator.py: 测试数据生成器
  - resource_monitor.py: 后台资源监控
  - report_generator.py: HTML/JSON 报告生成

用法：
    python -m tests.autonomous.run_autonomous
    python -m tests.autonomous.run_autonomous --resume
"""
