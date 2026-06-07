"""Tests for the configuration validators."""

from pipeforge.validator import (
    validate_dockerfile,
    validate_github_actions,
    validate_gitlab_ci,
    validate_yaml,
)


class TestYAMLValidator:
    def test_valid_yaml(self):
        result = validate_yaml("name: test\nversion: 1\n")
        assert result.is_valid is True

    def test_invalid_yaml(self):
        result = validate_yaml("name: [\ninvalid\n")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_empty_yaml(self):
        result = validate_yaml("")
        assert result.is_valid is True  # Empty is valid YAML
        assert len(result.warnings) > 0

    def test_non_mapping_root(self):
        result = validate_yaml("- item1\n- item2\n")
        assert result.is_valid is False


class TestGitHubActionsValidator:
    def test_valid_workflow(self):
        content = """name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo hello
"""
        result = validate_github_actions(content)
        assert result.is_valid is True

    def test_missing_on(self):
        content = """name: CI
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
"""
        result = validate_github_actions(content)
        assert result.is_valid is False

    def test_missing_jobs(self):
        content = """name: CI
on: push
"""
        result = validate_github_actions(content)
        assert result.is_valid is False

    def test_missing_runs_on(self):
        content = """name: CI
on: push
jobs:
  test:
    steps:
      - run: echo hello
"""
        result = validate_github_actions(content)
        assert result.is_valid is False

    def test_missing_steps(self):
        content = """name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
"""
        result = validate_github_actions(content)
        assert result.is_valid is False

    def test_unpinned_action_warning(self):
        content = """name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
      - run: echo hello
"""
        result = validate_github_actions(content)
        assert any("pin" in w.message.lower() for w in result.warnings)

    def test_missing_name_warning(self):
        content = """on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
"""
        result = validate_github_actions(content)
        assert any("name" in w.message.lower() for w in result.warnings)


class TestGitLabCIValidator:
    def test_valid_config(self):
        content = """stages:
  - test
  - build

test:
  stage: test
  script:
    - echo "test"
"""
        result = validate_gitlab_ci(content)
        assert result.is_valid is True

    def test_missing_stages_warning(self):
        content = """test:
  script:
    - echo "test"
"""
        result = validate_gitlab_ci(content)
        assert any("stages" in w.message.lower() for w in result.warnings)

    def test_invalid_stage_reference(self):
        content = """stages:
  - test

build:
  stage: deploy
  script:
    - echo "deploy"
"""
        result = validate_gitlab_ci(content)
        assert result.is_valid is False

    def test_missing_script(self):
        content = """stages:
  - test

test:
  stage: test
"""
        result = validate_gitlab_ci(content)
        assert result.is_valid is False


class TestDockerfileValidator:
    def test_valid_dockerfile(self):
        content = """FROM python:3.12-slim
WORKDIR /app
COPY . .
USER appuser
HEALTHCHECK CMD curl -f http://localhost/
CMD ["python", "main.py"]
"""
        result = validate_dockerfile(content)
        assert result.is_valid is True

    def test_missing_from(self):
        content = """WORKDIR /app
COPY . .
"""
        result = validate_dockerfile(content)
        assert result.is_valid is False

    def test_latest_tag_warning(self):
        content = """FROM python:latest
WORKDIR /app
"""
        result = validate_dockerfile(content)
        warnings = [i for i in result.issues if i.severity == "warning"]
        assert any("latest" in w.message for w in warnings)

    def test_no_user_info(self):
        content = """FROM python:3.12
WORKDIR /app
CMD ["python", "main.py"]
"""
        result = validate_dockerfile(content)
        infos = [i for i in result.issues if i.severity == "info"]
        assert any("USER" in i.message or "root" in i.message for i in infos)

    def test_no_healthcheck_info(self):
        content = """FROM python:3.12
WORKDIR /app
USER appuser
CMD ["python", "main.py"]
"""
        result = validate_dockerfile(content)
        infos = [i for i in result.issues if i.severity == "info"]
        assert any("HEALTHCHECK" in i.message for i in infos)

    def test_errors_property(self):
        content = """WORKDIR /app"""
        result = validate_dockerfile(content)
        assert len(result.errors) > 0

    def test_warnings_property(self):
        content = """FROM python:latest
WORKDIR /app
"""
        result = validate_dockerfile(content)
        assert len(result.warnings) > 0
