"""Tests for the PipeForge CLI."""

import json
import os
from pathlib import Path

from click.testing import CliRunner

from pipeforge.cli import cli


class TestCLIAnalyze:
    def test_analyze_python_project(self, python_project):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", str(python_project.root)])
        assert result.exit_code == 0
        assert "python" in result.output.lower()

    def test_analyze_default_dir(self, python_project, monkeypatch):
        monkeypatch.chdir(python_project.root)
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze"])
        assert result.exit_code == 0

    def test_analyze_invalid_path(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "/nonexistent/path"])
        assert result.exit_code != 0


class TestCLIGenerate:
    def test_generate_github_actions(self, python_project):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "generate", str(python_project.root),
            "--platform", "github_actions",
            "--no-security",
        ])
        assert result.exit_code == 0
        assert (python_project.root / ".github" / "workflows" / "ci.yml").exists()

    def test_generate_dry_run(self, python_project):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "generate", str(python_project.root),
            "--platform", "github_actions",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_generate_docker(self, python_project):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "generate", str(python_project.root),
            "--platform", "docker",
        ])
        assert result.exit_code == 0
        assert (python_project.root / "Dockerfile").exists()
        assert (python_project.root / ".dockerignore").exists()

    def test_generate_gitlab_ci(self, python_project):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "generate", str(python_project.root),
            "--platform", "gitlab_ci",
        ])
        assert result.exit_code == 0
        assert (python_project.root / ".gitlab-ci.yml").exists()

    def test_generate_multiple_platforms(self, python_project):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "generate", str(python_project.root),
            "--platform", "github_actions",
            "--platform", "docker",
            "--no-security",
        ])
        assert result.exit_code == 0

    def test_generate_with_deploy(self, python_project):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "generate", str(python_project.root),
            "--platform", "github_actions",
            "--deploy",
            "--deploy-provider", "vercel",
            "--no-security",
        ])
        assert result.exit_code == 0

    def test_generate_empty_project(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", str(tmp_path)])
        assert result.exit_code == 0
        assert "No supported languages" in result.output


class TestCLIValidate:
    def test_validate_valid_workflow(self, tmp_path):
        wf = tmp_path / ".github" / "workflows" / "ci.yml"
        wf.parent.mkdir(parents=True)
        wf.write_text("name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf)])
        assert result.exit_code == 0
        assert "VALID" in result.output

    def test_validate_invalid_workflow(self, tmp_path):
        wf = tmp_path / ".github" / "workflows" / "ci.yml"
        wf.parent.mkdir(parents=True)
        wf.write_text("name: CI\njobs:\n  test:\n    steps: []\n")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(wf)])
        assert result.exit_code == 1

    def test_validate_dockerfile(self, tmp_path):
        df = tmp_path / "Dockerfile"
        df.write_text("FROM python:3.12-slim\nWORKDIR /app\nUSER appuser\nHEALTHCHECK CMD curl localhost\nCMD [\"python\", \"app.py\"]\n")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(df)])
        assert result.exit_code == 0


class TestCLIInspect:
    def test_inspect_json_output(self, python_project):
        runner = CliRunner()
        result = runner.invoke(cli, ["inspect", str(python_project.root)])
        assert result.exit_code == 0
        # Output should contain JSON
        assert "languages" in result.output

    def test_inspect_invalid_path(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["inspect", "/nonexistent"])
        assert result.exit_code != 0


class TestCLIVersion:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output
