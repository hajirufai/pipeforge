"""GitLab CI configuration generator."""

from __future__ import annotations

from ..models import (
    DatabaseType,
    GeneratedFile,
    Language,
    Linter,
    PackageManager,
    TestRunner,
)
from .base import BaseGenerator


class GitLabCIGenerator(BaseGenerator):
    """Generates .gitlab-ci.yml configuration files."""

    platform_name = "GitLab CI"

    def generate(self) -> list[GeneratedFile]:
        lang = self.analysis.primary_language
        if lang == Language.PYTHON:
            content = self._python_pipeline()
        elif lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            content = self._node_pipeline()
        elif lang == Language.GO:
            content = self._go_pipeline()
        elif lang == Language.RUST:
            content = self._rust_pipeline()
        elif lang == Language.JAVA:
            content = self._java_pipeline()
        else:
            content = self._generic_pipeline()

        return [
            GeneratedFile(
                path=".gitlab-ci.yml",
                content=content,
                description="GitLab CI/CD pipeline with lint, test, build, and deploy stages",
            )
        ]

    def _python_pipeline(self) -> str:
        versions = self.config.python_versions
        has_poetry = PackageManager.POETRY in self.analysis.package_managers
        has_pytest = TestRunner.PYTEST in self.analysis.test_runners
        linters = self.analysis.linters
        databases = self.analysis.databases

        lines = [
            "stages:",
            "  - lint",
            "  - test",
            "  - build",
            "  - deploy",
            "",
            "variables:",
            f"  PIP_CACHE_DIR: \"$CI_PROJECT_DIR/.cache/pip\"",
            "",
            "cache:",
            "  paths:",
        ]

        if has_poetry:
            lines += ["    - .venv/", "    - .cache/pip/"]
        else:
            lines += ["    - .cache/pip/"]

        lines.append("")

        # Lint stage
        if linters:
            lines.append("lint:")
            lines.append("  stage: lint")
            lines.append(f"  image: python:{versions[0]}-slim")
            lines.append("  script:")
            if has_poetry:
                lines.append("    - pip install poetry")
                lines.append("    - poetry install --no-interaction")
                prefix = "poetry run "
            else:
                lines.append("    - pip install -r requirements.txt")
                lines.append("    - pip install -r requirements-dev.txt 2>/dev/null || true")
                prefix = ""

            if Linter.RUFF in linters:
                lines.append(f"    - {prefix}ruff check .")
                lines.append(f"    - {prefix}ruff format --check .")
            else:
                if Linter.BLACK in linters:
                    lines.append(f"    - {prefix}black --check .")
                if Linter.FLAKE8 in linters:
                    lines.append(f"    - {prefix}flake8 .")
            if Linter.MYPY in linters:
                lines.append(f"    - {prefix}mypy .")
            lines.append("")

        # Test stages (matrix via parallel jobs)
        for ver in versions:
            lines.append(f"test-python-{ver.replace('.', '')}:")
            lines.append("  stage: test")
            lines.append(f"  image: python:{ver}-slim")

            # Services
            if DatabaseType.POSTGRESQL in databases:
                lines += [
                    "  services:",
                    "    - name: postgres:16",
                    "      alias: postgres",
                    "  variables:",
                    "    POSTGRES_DB: testdb",
                    "    POSTGRES_USER: test",
                    "    POSTGRES_PASSWORD: test",
                    "    DATABASE_URL: \"postgresql://test:test@postgres:5432/testdb\"",
                ]

            lines.append("  script:")
            if has_poetry:
                lines.append("    - pip install poetry")
                lines.append("    - poetry install --no-interaction")
                test_cmd = "poetry run pytest --tb=short --cov --junitxml=report.xml"
            else:
                lines.append("    - pip install -r requirements.txt")
                lines.append("    - pip install -r requirements-dev.txt 2>/dev/null || true")
                test_cmd = "pytest --tb=short --cov --junitxml=report.xml" if has_pytest else "python -m unittest discover"

            lines.append(f"    - {test_cmd}")
            lines += [
                "  artifacts:",
                "    when: always",
                "    reports:",
                "      junit: report.xml",
                "    expire_in: 30 days",
                "",
            ]

        # Build stage
        if self.config.include_docker:
            lines += [
                "build-docker:",
                "  stage: build",
                "  image: docker:latest",
                "  services:",
                "    - docker:dind",
                "  variables:",
                "    DOCKER_TLS_CERTDIR: \"/certs\"",
                "  script:",
                "    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .",
                "    - docker tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA $CI_REGISTRY_IMAGE:latest",
                "    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY",
                "    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA",
                "    - docker push $CI_REGISTRY_IMAGE:latest",
                "  only:",
                "    - main",
                "",
            ]

        # Deploy stage
        if self.config.include_deploy:
            lines += [
                "deploy-staging:",
                "  stage: deploy",
                "  environment:",
                "    name: staging",
                "  script:",
                "    - echo \"Deploy to staging\"",
                "  only:",
                "    - main",
                "  when: manual",
                "",
                "deploy-production:",
                "  stage: deploy",
                "  environment:",
                "    name: production",
                "  script:",
                "    - echo \"Deploy to production\"",
                "  only:",
                "    - tags",
                "  when: manual",
                "",
            ]

        return "\n".join(lines)

    def _node_pipeline(self) -> str:
        versions = self.config.node_versions
        has_yarn = PackageManager.YARN in self.analysis.package_managers
        has_pnpm = PackageManager.PNPM in self.analysis.package_managers
        test_runner = next((t for t in self.analysis.test_runners
                          if t in (TestRunner.JEST, TestRunner.VITEST, TestRunner.MOCHA)), None)

        lines = [
            "stages:",
            "  - lint",
            "  - test",
            "  - build",
            "  - deploy",
            "",
            "cache:",
            "  paths:",
            "    - node_modules/",
            "",
        ]

        # Determine install command
        if has_pnpm:
            install = "npm install -g pnpm && pnpm install --frozen-lockfile"
            prefix = "pnpm "
        elif has_yarn:
            install = "yarn install --frozen-lockfile"
            prefix = "yarn "
        else:
            install = "npm ci"
            prefix = "npx "

        # Lint
        if Linter.ESLINT in self.analysis.linters:
            lines += [
                "lint:",
                "  stage: lint",
                f"  image: node:{versions[0]}-slim",
                "  script:",
                f"    - {install}",
                f"    - {prefix}eslint .",
                "",
            ]

        # Test matrix
        for ver in versions:
            lines += [
                f"test-node-{ver}:",
                "  stage: test",
                f"  image: node:{ver}-slim",
                "  script:",
                f"    - {install}",
            ]
            if test_runner:
                test_cmd = {
                    TestRunner.JEST: f"{prefix}jest --coverage",
                    TestRunner.VITEST: f"{prefix}vitest run --coverage",
                    TestRunner.MOCHA: f"{prefix}mocha",
                }.get(test_runner, f"{prefix}test")
                lines.append(f"    - {test_cmd}")
            lines += [
                "  artifacts:",
                "    when: always",
                "    expire_in: 30 days",
                "",
            ]

        # Build
        lines += [
            "build:",
            "  stage: build",
            f"  image: node:{versions[0]}-slim",
            "  script:",
            f"    - {install}",
            f"    - {prefix.strip()} run build",
            "  artifacts:",
            "    paths:",
            "      - dist/",
            "      - build/",
            "    expire_in: 7 days",
            "",
        ]

        return "\n".join(lines)

    def _go_pipeline(self) -> str:
        versions = self.config.go_versions
        linters = self.analysis.linters
        has_tests = TestRunner.GO_TEST in self.analysis.test_runners

        lines = [
            "stages:",
            "  - lint",
            "  - test",
            "  - build",
            "",
            "variables:",
            "  GOPATH: $CI_PROJECT_DIR/.go",
            "",
            "cache:",
            "  paths:",
            "    - .go/pkg/mod/",
            "",
        ]

        if Linter.GOLANGCI_LINT in linters:
            lines += [
                "lint:",
                "  stage: lint",
                f"  image: golangci/golangci-lint:latest",
                "  script:",
                "    - golangci-lint run ./...",
                "",
            ]

        for ver in versions:
            lines += [
                f"test-go-{ver.replace('.', '')}:",
                "  stage: test",
                f"  image: golang:{ver}",
                "  script:",
                "    - go mod download",
            ]
            if has_tests:
                lines.append("    - go test -race -coverprofile=coverage.out -covermode=atomic ./...")
            lines += [
                "  artifacts:",
                "    paths:",
                "      - coverage.out",
                "    expire_in: 30 days",
                "",
            ]

        lines += [
            "build:",
            "  stage: build",
            f"  image: golang:{versions[0]}",
            "  script:",
            "    - go build -o app ./...",
            "  artifacts:",
            "    paths:",
            "      - app",
            "    expire_in: 7 days",
            "",
        ]

        return "\n".join(lines)

    def _rust_pipeline(self) -> str:
        linters = self.analysis.linters
        has_tests = TestRunner.CARGO_TEST in self.analysis.test_runners

        lines = [
            "stages:",
            "  - lint",
            "  - test",
            "  - build",
            "",
            "cache:",
            "  paths:",
            "    - target/",
            "    - $CARGO_HOME/registry/",
            "",
        ]

        if Linter.RUSTFMT in linters or Linter.CLIPPY in linters:
            lines += ["lint:", "  stage: lint", "  image: rust:latest", "  script:"]
            if Linter.RUSTFMT in linters:
                lines.append("    - cargo fmt --all -- --check")
            if Linter.CLIPPY in linters:
                lines.append("    - cargo clippy -- -D warnings")
            lines.append("")

        lines += [
            "test:",
            "  stage: test",
            "  image: rust:latest",
            "  script:",
        ]
        if has_tests:
            lines.append("    - cargo test --verbose")
        lines += ["", "build:", "  stage: build", "  image: rust:latest", "  script:",
                   "    - cargo build --release", "  artifacts:", "    paths:",
                   "      - target/release/", "    expire_in: 7 days", ""]

        return "\n".join(lines)

    def _java_pipeline(self) -> str:
        versions = self.config.java_versions
        has_maven = PackageManager.MAVEN in self.analysis.package_managers
        has_gradle = PackageManager.GRADLE in self.analysis.package_managers

        lines = [
            "stages:",
            "  - test",
            "  - build",
            "",
        ]

        for ver in versions:
            lines += [
                f"test-java-{ver}:",
                "  stage: test",
                f"  image: eclipse-temurin:{ver}",
                "  script:",
            ]
            if has_gradle:
                lines.append("    - ./gradlew test")
            elif has_maven:
                lines.append("    - mvn verify")
            lines.append("")

        build_cmd = "./gradlew build" if has_gradle else "mvn package -DskipTests"
        lines += [
            "build:",
            "  stage: build",
            f"  image: eclipse-temurin:{versions[0]}",
            "  script:",
            f"    - {build_cmd}",
            "  artifacts:",
            "    paths:",
            "      - build/libs/" if has_gradle else "      - target/",
            "    expire_in: 7 days",
            "",
        ]

        return "\n".join(lines)

    def _generic_pipeline(self) -> str:
        return """stages:
  - test
  - build

test:
  stage: test
  script:
    - echo "Add your test commands here"

build:
  stage: build
  script:
    - echo "Add your build commands here"
"""
