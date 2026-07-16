#!/usr/bin/env python3
"""
CLI 命令测试 — 命令解析、参数校验、边界条件

测试范围：
  - CLI 命令解析（run, resume, status, config）
  - 无效参数处理
  - 不存在的文件
  - 帮助信息输出
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCLIParsing:
    """CLI 参数解析"""

    def test_help_output(self, capsys):
        """--help 输出帮助信息"""
        from cli import main

        with patch("sys.argv", ["cli.py", "--help"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 0

        captured = capsys.readouterr()
        assert "run" in captured.out or "run" in captured.err
        assert "resume" in captured.out or "resume" in captured.err

    def test_no_command_shows_help(self, capsys):
        """无命令时显示帮助"""
        from cli import main

        with patch("sys.argv", ["cli.py"]):
            result = main()
            assert result == 1

    def test_run_command_parsing(self):
        """run 命令参数解析"""
        from cli import main

        with patch("sys.argv", ["cli.py", "run", "/tmp/test.md"]):
            with patch("cli.cmd_run", return_value=0) as mock_run:
                result = main()
                assert result == 0
                mock_run.assert_called_once()

    def test_run_with_options(self):
        """run 命令带选项"""
        from cli import main

        with patch("sys.argv", [
            "cli.py", "run", "/tmp/test.md",
            "--mode", "auto",
            "-d", "all",
            "-f", "excel,xmind",
            "-o", "/tmp/output",
        ]):
            with patch("cli.cmd_run", return_value=0) as mock_run:
                result = main()
                assert result == 0
                call_args = mock_run.call_args[0][0]
                assert call_args.mode == "auto"
                assert call_args.dimensions == "all"
                assert call_args.formats == "excel,xmind"
                assert call_args.output == "/tmp/output"

    def test_resume_command(self):
        """resume 命令"""
        from cli import main

        with patch("sys.argv", ["cli.py", "resume", "-o", "/tmp/output"]):
            with patch("cli.cmd_resume", return_value=0) as mock_resume:
                result = main()
                assert result == 0
                mock_resume.assert_called_once()

    def test_status_command(self):
        """status 命令"""
        from cli import main

        with patch("sys.argv", ["cli.py", "status"]):
            with patch("cli.cmd_status", return_value=0) as mock_status:
                result = main()
                assert result == 0
                mock_status.assert_called_once()

    def test_config_command(self):
        """config 命令"""
        from cli import main

        with patch("sys.argv", ["cli.py", "config"]):
            with patch("cli.cmd_config", return_value=0) as mock_config:
                result = main()
                assert result == 0
                mock_config.assert_called_once()


class TestCMDRun:
    """cmd_run 函数测试"""

    def test_run_file_not_found(self, capsys):
        """需求文件不存在"""
        import argparse

        from cli import cmd_run
        args = argparse.Namespace(
            requirements="/nonexistent/file.md",
            output="/tmp/output",
            mode=None,
            dimensions=None,
            formats=None,
            config=None,
        )

        with patch("cli._load_and_validate", return_value={"llm": {"api_key": "sk-test", "base_url": "url", "model": "m"}}):
            result = cmd_run(args)
            assert result == 1

    def test_run_config_validation_fails(self, capsys):
        """配置校验失败"""
        import argparse

        from cli import cmd_run
        args = argparse.Namespace(
            requirements="/tmp/test.md",
            output="/tmp/output",
            mode=None,
            dimensions=None,
            formats=None,
            config=None,
        )

        with patch("cli._load_and_validate", return_value=None):
            result = cmd_run(args)
            assert result == 1


class TestCMDConfig:
    """cmd_config 函数测试"""

    def test_config_output(self, capsys):
        """config 命令输出"""
        import argparse

        from cli import cmd_config
        args = argparse.Namespace(config=None)

        with patch("cli.load_config", return_value={
            "llm": {
                "provider": "test", "model": "test-model",
                "base_url": "https://test.com", "api_key": "sk-test-key-12345678",
            },
            "knowledge_base": {"enabled": True, "vault_path": "/test"},
            "pipeline": {
                "default_mode": "semi", "default_dimensions": "basic",
                "default_formats": "excel", "self_check": True,
            },
        }):
            result = cmd_config(args)
            assert result == 0

        captured = capsys.readouterr()
        assert "test" in captured.out or "test" in captured.err


class TestCMDStatus:
    """cmd_status 函数测试"""

    def test_status_output(self, capsys):
        """status 命令输出"""
        import argparse

        from cli import cmd_status
        args = argparse.Namespace(output="/tmp/output", config=None)

        with patch("cli.load_config", return_value={"llm": {}, "pipeline": {}}):
            with patch("cli.Pipeline") as mock_pipeline:
                mock_instance = MagicMock()
                mock_pipeline.return_value = mock_instance
                result = cmd_status(args)
                assert result == 0
                mock_instance.status.assert_called_once()


class TestLoadAndValidate:
    """_load_and_validate 函数"""

    def test_valid_config(self):
        """有效配置返回配置字典"""
        from cli import _load_and_validate

        with patch("cli.load_config", return_value={
            "llm": {"api_key": "sk-test", "base_url": "url", "model": "m"},
            "pipeline": {},
        }):
            with patch("cli.validate_config", return_value=[]):
                result = _load_and_validate("")
                assert result is not None
                assert "llm" in result

    def test_invalid_config(self):
        """无效配置返回 None"""
        from cli import _load_and_validate

        with patch("cli.load_config", return_value={}):
            with patch("cli.validate_config", return_value=["error1"]):
                result = _load_and_validate("")
                assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
