"""GitHub Actions workflow generator."""

from __future__ import annotations

from ..models import (
    DatabaseType,
    Framework,
    GeneratedFile,
    GeneratorConfig,
    Language,
    Linter,
    PackageManager,
    ProjectAnalysis,
    TestRunner,
)
from .base import BaseGenerator


class GitHubActionsGenerator(BaseGenerator):
    """Generates GitHub Actions CI/CD workflows."""

    platform_name = "GitHub Actions"

    def generate(self) -> list[GeneratedFile]:
        files = []
        files.append(self._generate_ci_workflow())
        if self.config.include_security:
            files.append(self._generate_codeql_workflow())
        if self.config.include_deploy:
            files.append(self._generate_deploy_workflow())
        return files

    def _generate_ci_workflow(self) -> GeneratedFile:
        """Generate the main CI workflow."""
        lang = self.analysis.primary_language

        jobs = []
        if lang == Language.PYTHON:
            jobs.append(self._python_ci_job())
        elif lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            jobs.append(self._node_ci_job())
        elif lang == Language.GO:
            jobs.append(self._go_ci_job())
        elif lang == Language.RUST:
            jobs.append(self._rust_ci_job())
        elif lang == Language.JAVA:
            jobs.append(self._java_ci_job())

        content = self._build_workflow(
            name="CI",
            triggers=["push", "pull_request"],
            jobs=jobs,
        )

        return GeneratedFile(
            path=".github/workflows/ci.yml",
            content=content,
            description="Continuous Integration workflow with linting, testing, and coverage",
        )

    def _generate_codeql_workflow(self) -> GeneratedFile:
        """Generate CodeQL security analysis workflow."""
        lang = self.analysis.primary_language
        codeql_lang = {
            Language.PYTHON: "python",
            Language.JAVASCRIPT: "javascript-typescript",
            Language.TYPESCRIPT: "javascript-typescript",
            Language.GO: "go",
            Language.JAVA: "java-kotlin",
            Language.RUST: "cpp",  # Rust uses C++ analyzer
        }.get(lang, "python")

        content = f"""name: CodeQL Analysis

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday

jobs:
  analyze:
    name: Analyze
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write

    strategy:
      fail-fast: false
      matrix:
        language: ['{codeql_lang}']

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: ${{{{ matrix.language }}}}

      - name: Autobuild
        uses: github/codeql-action/autobuild@v3

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
        with:
          category: "/language:${{{{ matrix.language }}}}"
"""
        return GeneratedFile(
            path=".github/workflows/codeql.yml",
            content=content,
            description="CodeQL security scanning (runs on push, PR, and weekly)",
        )

    def _generate_deploy_workflow(self) -> GeneratedFile:
        """Generate a deployment workflow."""
        provider = self.config.deploy_provider or "generic"
        deploy_step = self._get_deploy_step(provider)

        content = f"""name: Deploy

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  deploy:
    name: Deploy to {provider.title()}
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/')
    environment:
      name: ${{{{ startsWith(github.ref, 'refs/tags/') && 'production' || 'staging' }}}}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

{deploy_step}
"""
        return GeneratedFile(
            path=".github/workflows/deploy.yml",
            content=content,
            description=f"Deployment workflow for {provider.title()}",
        )

    def _python_ci_job(self) -> dict:
        """Build a Python CI job configuration."""
        versions = self.config.python_versions
        has_poetry = PackageManager.POETRY in self.analysis.package_managers
        has_pytest = TestRunner.PYTEST in self.analysis.test_runners
        linters = self.analysis.linters
        databases = self.analysis.databases

        # Build steps
        steps = [
            {"name": "Checkout", "uses": "actions/checkout@v4"},
            {
                "name": "Set up Python ${{ matrix.python-version }}",
                "uses": "actions/setup-python@v5",
                "with": {"python-version": "${{ matrix.python-version }}"},
            },
        ]

        # Caching
        if has_poetry:
            steps.append({
                "name": "Install Poetry",
                "uses": "snoks/install-poetry@v1",
                "with": {"virtualenvs-create": "true", "virtualenvs-in-project": "true"},
            })
            steps.append({
                "name": "Cache Poetry virtualenv",
                "uses": "actions/cache@v4",
                "with": {
                    "path": ".venv",
                    "key": "${{ runner.os }}-poetry-${{ matrix.python-version }}-${{ hashFiles('**/poetry.lock') }}",
                    "restore-keys": "${{ runner.os }}-poetry-${{ matrix.python-version }}-",
                },
            })
            steps.append({"name": "Install dependencies", "run": "poetry install --no-interaction"})
        else:
            steps.append({
                "name": "Cache pip",
                "uses": "actions/cache@v4",
                "with": {
                    "path": "~/.cache/pip",
                    "key": "${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('**/requirements*.txt') }}",
                    "restore-keys": "${{ runner.os }}-pip-${{ matrix.python-version }}-",
                },
            })
            install_cmd = "pip install -r requirements.txt"
            if has_pytest:
                install_cmd += "\npip install -r requirements-dev.txt 2>/dev/null || true"
            steps.append({"name": "Install dependencies", "run": install_cmd})

        # Linting
        prefix = "poetry run " if has_poetry else ""
        if Linter.RUFF in linters:
            steps.append({"name": "Lint with Ruff", "run": f"{prefix}ruff check ."})
            steps.append({"name": "Format check with Ruff", "run": f"{prefix}ruff format --check ."})
        else:
            if Linter.BLACK in linters:
                steps.append({"name": "Format check with Black", "run": f"{prefix}black --check ."})
            if Linter.FLAKE8 in linters:
                steps.append({"name": "Lint with Flake8", "run": f"{prefix}flake8 ."})
        if Linter.MYPY in linters:
            steps.append({"name": "Type check with MyPy", "run": f"{prefix}mypy ."})

        # Testing
        if has_pytest:
            test_cmd = f"{prefix}pytest --tb=short --cov --cov-report=term-missing"
            steps.append({"name": "Run tests", "run": test_cmd})

        return {
            "name": "test",
            "display_name": "Test (Python ${{ matrix.python-version }})",
            "runs_on": "ubuntu-latest",
            "strategy_matrix": {"python-version": versions},
            "services": self._get_db_services(databases),
            "steps": steps,
        }

    def _node_ci_job(self) -> dict:
        """Build a Node.js CI job configuration."""
        versions = self.config.node_versions
        has_yarn = PackageManager.YARN in self.analysis.package_managers
        has_pnpm = PackageManager.PNPM in self.analysis.package_managers
        test_runner = next((t for t in self.analysis.test_runners
                          if t in (TestRunner.JEST, TestRunner.VITEST, TestRunner.MOCHA)), None)
        linters = self.analysis.linters

        steps = [
            {"name": "Checkout", "uses": "actions/checkout@v4"},
            {
                "name": "Set up Node.js ${{ matrix.node-version }}",
                "uses": "actions/setup-node@v4",
                "with": {"node-version": "${{ matrix.node-version }}", "cache": "npm" if not has_yarn else "yarn"},
            },
        ]

        # Install
        if has_pnpm:
            steps.append({"name": "Install pnpm", "uses": "pnpm/action-setup@v2", "with": {"version": "latest"}})
            steps.append({"name": "Install dependencies", "run": "pnpm install --frozen-lockfile"})
            prefix = "pnpm "
        elif has_yarn:
            steps.append({"name": "Install dependencies", "run": "yarn install --frozen-lockfile"})
            prefix = "yarn "
        else:
            steps.append({"name": "Install dependencies", "run": "npm ci"})
            prefix = "npx "

        # Lint
        if Linter.ESLINT in linters:
            steps.append({"name": "Lint", "run": f"{prefix}eslint ."})
        if Linter.PRETTIER in linters:
            steps.append({"name": "Format check", "run": f"{prefix}prettier --check ."})

        # Test
        if test_runner:
            steps.append({"name": "Run tests", "run": f"{prefix}{'jest --coverage' if test_runner == TestRunner.JEST else 'vitest run --coverage' if test_runner == TestRunner.VITEST else 'mocha'}"})

        # Build (for TypeScript / Next.js)
        if Language.TYPESCRIPT in [l.language for l in self.analysis.languages] or Framework.NEXTJS in self.analysis.frameworks:
            steps.append({"name": "Build", "run": f"{prefix.strip()} run build" if not has_pnpm else "pnpm build"})

        return {
            "name": "test",
            "display_name": "Test (Node.js ${{ matrix.node-version }})",
            "runs_on": "ubuntu-latest",
            "strategy_matrix": {"node-version": versions},
            "services": {},
            "steps": steps,
        }

    def _go_ci_job(self) -> dict:
        """Build a Go CI job configuration."""
        versions = self.config.go_versions
        linters = self.analysis.linters
        has_tests = TestRunner.GO_TEST in self.analysis.test_runners

        steps = [
            {"name": "Checkout", "uses": "actions/checkout@v4"},
            {
                "name": "Set up Go ${{ matrix.go-version }}",
                "uses": "actions/setup-go@v5",
                "with": {"go-version": "${{ matrix.go-version }}"},
            },
            {"name": "Download dependencies", "run": "go mod download"},
            {"name": "Verify dependencies", "run": "go mod verify"},
        ]

        if Linter.GOLANGCI_LINT in linters:
            steps.append({
                "name": "Lint",
                "uses": "golangci/golangci-lint-action@v4",
                "with": {"version": "latest"},
            })

        steps.append({"name": "Build", "run": "go build -v ./..."})

        if has_tests:
            steps.append({"name": "Test", "run": "go test -race -coverprofile=coverage.out -covermode=atomic ./..."})
            steps.append({"name": "Upload coverage", "uses": "codecov/codecov-action@v4", "with": {"files": "coverage.out"}})

        return {
            "name": "test",
            "display_name": "Test (Go ${{ matrix.go-version }})",
            "runs_on": "ubuntu-latest",
            "strategy_matrix": {"go-version": versions},
            "services": {},
            "steps": steps,
        }

    def _rust_ci_job(self) -> dict:
        """Build a Rust CI job configuration."""
        linters = self.analysis.linters
        has_tests = TestRunner.CARGO_TEST in self.analysis.test_runners

        steps = [
            {"name": "Checkout", "uses": "actions/checkout@v4"},
            {
                "name": "Install Rust toolchain",
                "uses": "dtolnay/rust-toolchain@stable",
                "with": {"components": "rustfmt, clippy"},
            },
            {
                "name": "Cache cargo",
                "uses": "actions/cache@v4",
                "with": {
                    "path": "~/.cargo/registry\n~/.cargo/git\ntarget",
                    "key": "${{ runner.os }}-cargo-${{ hashFiles('**/Cargo.lock') }}",
                },
            },
        ]

        if Linter.RUSTFMT in linters:
            steps.append({"name": "Check formatting", "run": "cargo fmt --all -- --check"})
        if Linter.CLIPPY in linters:
            steps.append({"name": "Clippy", "run": "cargo clippy -- -D warnings"})

        steps.append({"name": "Build", "run": "cargo build --verbose"})

        if has_tests:
            steps.append({"name": "Test", "run": "cargo test --verbose"})

        return {
            "name": "test",
            "display_name": "Test (Rust stable)",
            "runs_on": "ubuntu-latest",
            "strategy_matrix": {},
            "services": {},
            "steps": steps,
        }

    def _java_ci_job(self) -> dict:
        """Build a Java CI job configuration."""
        versions = self.config.java_versions
        has_maven = PackageManager.MAVEN in self.analysis.package_managers
        has_gradle = PackageManager.GRADLE in self.analysis.package_managers

        steps = [
            {"name": "Checkout", "uses": "actions/checkout@v4"},
            {
                "name": "Set up JDK ${{ matrix.java-version }}",
                "uses": "actions/setup-java@v4",
                "with": {
                    "java-version": "${{ matrix.java-version }}",
                    "distribution": "temurin",
                },
            },
        ]

        if has_gradle:
            steps.append({"name": "Setup Gradle", "uses": "gradle/actions/setup-gradle@v3"})
            steps.append({"name": "Build and Test", "run": "./gradlew build"})
        elif has_maven:
            steps.append({"name": "Build and Test", "run": "mvn -B verify"})

        return {
            "name": "test",
            "display_name": "Test (Java ${{ matrix.java-version }})",
            "runs_on": "ubuntu-latest",
            "strategy_matrix": {"java-version": versions},
            "services": {},
            "steps": steps,
        }

    def _build_workflow(self, name: str, triggers: list[str], jobs: list[dict]) -> str:
        """Build a complete workflow YAML string."""
        lines = [f"name: {name}", "", "on:"]
        for trigger in triggers:
            if trigger in ("push", "pull_request"):
                lines.append(f"  {trigger}:")
                lines.append("    branches: [main]")
        lines.append("")

        lines.append("jobs:")
        for job in jobs:
            job_name = job["name"]
            lines.append(f"  {job_name}:")
            lines.append(f"    name: {job['display_name']}")
            lines.append(f"    runs-on: {job['runs_on']}")

            # Strategy matrix
            if job.get("strategy_matrix"):
                lines.append("    strategy:")
                lines.append("      matrix:")
                for key, values in job["strategy_matrix"].items():
                    lines.append(f"        {key}: {values}")

            # Services (databases)
            if job.get("services"):
                lines.append("    services:")
                for svc_name, svc_config in job["services"].items():
                    lines.append(f"      {svc_name}:")
                    lines.append(f"        image: {svc_config['image']}")
                    if svc_config.get("env"):
                        lines.append("        env:")
                        for k, v in svc_config["env"].items():
                            lines.append(f"          {k}: {v}")
                    if svc_config.get("ports"):
                        lines.append("        ports:")
                        for port in svc_config["ports"]:
                            lines.append(f"          - {port}")
                    if svc_config.get("options"):
                        lines.append(f"        options: {svc_config['options']}")

            lines.append("    steps:")
            for step in job["steps"]:
                if "uses" in step:
                    lines.append(f"      - name: {step['name']}")
                    lines.append(f"        uses: {step['uses']}")
                    if "with" in step:
                        lines.append("        with:")
                        for k, v in step["with"].items():
                            if "\n" in str(v):
                                lines.append(f"          {k}: |")
                                for vline in str(v).split("\n"):
                                    lines.append(f"            {vline}")
                            else:
                                lines.append(f"          {k}: {v}")
                elif "run" in step:
                    lines.append(f"      - name: {step['name']}")
                    run_val = step["run"]
                    if "\n" in run_val:
                        lines.append("        run: |")
                        for rline in run_val.split("\n"):
                            lines.append(f"          {rline}")
                    else:
                        lines.append(f"        run: {run_val}")

            lines.append("")

        return "\n".join(lines)

    def _get_db_services(self, databases: list[DatabaseType]) -> dict:
        """Get GitHub Actions service containers for databases."""
        services = {}
        if DatabaseType.POSTGRESQL in databases:
            services["postgres"] = {
                "image": "postgres:16",
                "env": {
                    "POSTGRES_USER": "test",
                    "POSTGRES_PASSWORD": "test",
                    "POSTGRES_DB": "testdb",
                },
                "ports": ["5432:5432"],
                "options": "--health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5",
            }
        if DatabaseType.REDIS in databases:
            services["redis"] = {
                "image": "redis:7",
                "ports": ["6379:6379"],
                "options": "--health-cmd 'redis-cli ping' --health-interval 10s --health-timeout 5s --health-retries 5",
            }
        if DatabaseType.MYSQL in databases:
            services["mysql"] = {
                "image": "mysql:8",
                "env": {
                    "MYSQL_ROOT_PASSWORD": "test",
                    "MYSQL_DATABASE": "testdb",
                },
                "ports": ["3306:3306"],
                "options": "--health-cmd 'mysqladmin ping' --health-interval 10s --health-timeout 5s --health-retries 5",
            }
        return services

    def _get_deploy_step(self, provider: str) -> str:
        """Get deployment step for a specific provider."""
        if provider == "vercel":
            return """      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: ${{ startsWith(github.ref, 'refs/tags/') && '--prod' || '' }}"""
        elif provider == "heroku":
            return """      - name: Deploy to Heroku
        uses: akhileshns/heroku-deploy@v3.13.15
        with:
          heroku_api_key: ${{ secrets.HEROKU_API_KEY }}
          heroku_app_name: ${{ secrets.HEROKU_APP_NAME }}
          heroku_email: ${{ secrets.HEROKU_EMAIL }}"""
        else:
            return """      - name: Build artifact
        run: echo "Build your deployment artifact here"

      - name: Deploy
        run: echo "Add your deployment commands here"
        env:
          DEPLOY_ENV: ${{ startsWith(github.ref, 'refs/tags/') && 'production' || 'staging' }}"""
