"""Tests for the GitHub Actions generator."""

import yaml

from pipeforge.analyzer import analyze_project
from pipeforge.generators.github_actions import GitHubActionsGenerator
from pipeforge.models import GeneratorConfig


class TestGitHubActionsGenerator:
    def test_generates_ci_workflow(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci_file = next(f for f in files if "ci.yml" in f.path)
        assert ci_file is not None
        assert "name: CI" in ci_file.content
        assert "actions/checkout@v4" in ci_file.content

    def test_python_matrix(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig(python_versions=["3.11", "3.12"])
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci = next(f for f in files if "ci.yml" in f.path)
        assert "3.11" in ci.content
        assert "3.12" in ci.content

    def test_python_pip_caching(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci = next(f for f in files if "ci.yml" in f.path)
        assert "cache" in ci.content.lower()

    def test_python_linting_steps(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci = next(f for f in files if "ci.yml" in f.path)
        assert "ruff" in ci.content.lower() or "flake8" in ci.content.lower()

    def test_python_pytest_step(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci = next(f for f in files if "ci.yml" in f.path)
        assert "pytest" in ci.content

    def test_node_workflow(self, node_project):
        analysis = analyze_project(str(node_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci = next(f for f in files if "ci.yml" in f.path)
        assert "setup-node" in ci.content
        assert "npm ci" in ci.content

    def test_node_jest(self, node_project):
        analysis = analyze_project(str(node_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci = next(f for f in files if "ci.yml" in f.path)
        assert "jest" in ci.content.lower()

    def test_go_workflow(self, go_project):
        analysis = analyze_project(str(go_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci = next(f for f in files if "ci.yml" in f.path)
        assert "setup-go" in ci.content
        assert "go test" in ci.content

    def test_codeql_included_by_default(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        codeql_files = [f for f in files if "codeql" in f.path]
        assert len(codeql_files) == 1

    def test_codeql_excluded(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig(include_security=False)
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        codeql_files = [f for f in files if "codeql" in f.path]
        assert len(codeql_files) == 0

    def test_deploy_workflow(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig(include_deploy=True, deploy_provider="vercel")
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        deploy_files = [f for f in files if "deploy" in f.path]
        assert len(deploy_files) == 1
        assert "vercel" in deploy_files[0].content.lower()

    def test_platform_name(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        assert gen.platform_name == "GitHub Actions"

    def test_rust_workflow(self, tmp_project):
        tmp_project.add_rust_project()
        analysis = analyze_project(str(tmp_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci = next(f for f in files if "ci.yml" in f.path)
        assert "cargo" in ci.content
        assert "clippy" in ci.content

    def test_java_workflow(self, tmp_project):
        tmp_project.add_java_project()
        analysis = analyze_project(str(tmp_project.root))
        config = GeneratorConfig()
        gen = GitHubActionsGenerator(analysis, config)
        files = gen.generate()

        ci = next(f for f in files if "ci.yml" in f.path)
        assert "setup-java" in ci.content
