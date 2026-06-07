"""Tests for the GitLab CI generator."""

from pipeforge.analyzer import analyze_project
from pipeforge.generators.gitlab_ci import GitLabCIGenerator
from pipeforge.models import GeneratorConfig


class TestGitLabCIGenerator:
    def test_generates_gitlab_ci(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitLabCIGenerator(analysis, config)
        files = gen.generate()

        assert len(files) == 1
        assert files[0].path == ".gitlab-ci.yml"

    def test_python_stages(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitLabCIGenerator(analysis, config)
        files = gen.generate()

        content = files[0].content
        assert "stages:" in content
        assert "lint" in content
        assert "test" in content

    def test_python_cache(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitLabCIGenerator(analysis, config)
        files = gen.generate()

        assert "cache:" in files[0].content

    def test_python_multi_version(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig(python_versions=["3.11", "3.12"])
        gen = GitLabCIGenerator(analysis, config)
        files = gen.generate()

        content = files[0].content
        assert "python:3.11" in content
        assert "python:3.12" in content

    def test_node_pipeline(self, node_project):
        analysis = analyze_project(str(node_project.root))
        config = GeneratorConfig()
        gen = GitLabCIGenerator(analysis, config)
        files = gen.generate()

        content = files[0].content
        assert "node:" in content
        assert "npm ci" in content

    def test_go_pipeline(self, go_project):
        analysis = analyze_project(str(go_project.root))
        config = GeneratorConfig()
        gen = GitLabCIGenerator(analysis, config)
        files = gen.generate()

        content = files[0].content
        assert "golang:" in content
        assert "go mod download" in content

    def test_rust_pipeline(self, tmp_project):
        tmp_project.add_rust_project()
        analysis = analyze_project(str(tmp_project.root))
        config = GeneratorConfig()
        gen = GitLabCIGenerator(analysis, config)
        files = gen.generate()

        content = files[0].content
        assert "rust" in content.lower()
        assert "cargo" in content

    def test_platform_name(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = GitLabCIGenerator(analysis, config)
        assert gen.platform_name == "GitLab CI"

    def test_docker_build_stage(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig(include_docker=True)
        gen = GitLabCIGenerator(analysis, config)
        files = gen.generate()

        content = files[0].content
        assert "docker" in content.lower()
