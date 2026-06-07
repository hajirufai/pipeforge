"""Project analysis engine — detects languages, frameworks, and tooling."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .models import (
    DatabaseType,
    Framework,
    Language,
    LanguageInfo,
    Linter,
    PackageManager,
    ProjectAnalysis,
    TestRunner,
)

# Directories to skip during analysis
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", ".next",
    "target", "vendor", ".gradle", ".idea", ".vscode",
}

# File extensions → Language mapping
EXTENSION_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".java": Language.JAVA,
}


def analyze_project(project_path: str) -> ProjectAnalysis:
    """Analyze a project directory and return detection results.

    Args:
        project_path: Path to the project root directory.

    Returns:
        ProjectAnalysis with detected languages, frameworks, etc.
    """
    root = Path(project_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {project_path}")

    analysis = ProjectAnalysis(
        project_name=root.name,
        project_path=str(root),
    )

    # Collect all relevant files
    files_by_ext: dict[str, list[Path]] = {}
    all_files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            all_files.append(fpath)
            ext = fpath.suffix.lower()
            if ext in EXTENSION_MAP:
                files_by_ext.setdefault(ext, []).append(fpath)

    # --- Language detection ---
    lang_counts: dict[Language, int] = {}
    for ext, fpaths in files_by_ext.items():
        lang = EXTENSION_MAP[ext]
        lang_counts[lang] = lang_counts.get(lang, 0) + len(fpaths)

    # Sort by file count (primary = most files)
    sorted_langs = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (lang, count) in enumerate(sorted_langs):
        analysis.languages.append(
            LanguageInfo(language=lang, file_count=count, is_primary=(i == 0))
        )

    # --- Config file detection ---
    file_names = {f.name for f in all_files}
    file_name_to_path = {f.name: f for f in all_files}

    # Package managers
    analysis.package_managers = _detect_package_managers(file_names)

    # --- Framework detection (requires reading file contents) ---
    analysis.frameworks = _detect_frameworks(root, file_names, file_name_to_path)

    # --- Test runner detection ---
    analysis.test_runners = _detect_test_runners(root, file_names, file_name_to_path, all_files)

    # --- Linter detection ---
    analysis.linters = _detect_linters(file_names, file_name_to_path)

    # --- Database detection ---
    analysis.databases = _detect_databases(root, file_names, file_name_to_path)

    # --- Docker detection ---
    docker_files = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"}
    analysis.has_docker = bool(file_names & docker_files)

    # --- Existing CI detection ---
    ci_indicators = {".github", ".gitlab-ci.yml", ".circleci", "Jenkinsfile", ".travis.yml"}
    has_github_dir = (root / ".github" / "workflows").is_dir()
    has_other_ci = bool(file_names & ci_indicators)
    analysis.has_ci = has_github_dir or has_other_ci

    # --- Entry points ---
    analysis.entry_points = _detect_entry_points(file_names, analysis)

    # --- Port detection ---
    analysis.port = _detect_port(root, file_name_to_path, analysis)

    return analysis


def _detect_package_managers(file_names: set[str]) -> list[PackageManager]:
    """Detect package managers from config file presence."""
    managers = []
    pm_map = [
        ({"pyproject.toml"}, PackageManager.POETRY, lambda fn: True),
        ({"Pipfile"}, PackageManager.PIPENV, lambda fn: True),
        ({"requirements.txt", "setup.py", "setup.cfg"}, PackageManager.PIP, lambda fn: True),
        ({"pnpm-lock.yaml"}, PackageManager.PNPM, lambda fn: True),
        ({"yarn.lock"}, PackageManager.YARN, lambda fn: True),
        ({"package.json", "package-lock.json"}, PackageManager.NPM, lambda fn: True),
        ({"Cargo.toml"}, PackageManager.CARGO, lambda fn: True),
        ({"go.mod"}, PackageManager.GO_MOD, lambda fn: True),
        ({"pom.xml"}, PackageManager.MAVEN, lambda fn: True),
        ({"build.gradle", "build.gradle.kts"}, PackageManager.GRADLE, lambda fn: True),
    ]

    detected = set()
    for indicators, pm, check in pm_map:
        if file_names & indicators and pm not in detected:
            managers.append(pm)
            detected.add(pm)

    # Deduplicate: if poetry detected, remove pip
    if PackageManager.POETRY in detected and PackageManager.PIP in detected:
        managers = [m for m in managers if m != PackageManager.PIP]

    return managers


def _detect_frameworks(
    root: Path, file_names: set[str], file_name_to_path: dict[str, Path]
) -> list[Framework]:
    """Detect frameworks by analyzing file contents and dependencies."""
    frameworks = []

    # Python frameworks — check imports in .py files
    py_content = _read_sample_files(root, "*.py", max_files=20)

    if any("from fastapi" in c or "import fastapi" in c for c in py_content):
        frameworks.append(Framework.FASTAPI)
    if any("from django" in c or "import django" in c for c in py_content) or "manage.py" in file_names:
        frameworks.append(Framework.DJANGO)
    if any("from flask" in c or "import flask" in c for c in py_content):
        frameworks.append(Framework.FLASK)

    # Node.js frameworks — check package.json
    if "package.json" in file_name_to_path:
        try:
            pkg = json.loads(file_name_to_path["package.json"].read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps:
                frameworks.append(Framework.NEXTJS)
            if "express" in deps:
                frameworks.append(Framework.EXPRESS)
        except (json.JSONDecodeError, OSError):
            pass

    # Go frameworks — check go.mod
    if "go.mod" in file_name_to_path:
        try:
            gomod = file_name_to_path["go.mod"].read_text()
            if "github.com/gin-gonic/gin" in gomod:
                frameworks.append(Framework.GIN)
        except OSError:
            pass

    # Rust frameworks — check Cargo.toml
    if "Cargo.toml" in file_name_to_path:
        try:
            cargo = file_name_to_path["Cargo.toml"].read_text()
            if "actix-web" in cargo:
                frameworks.append(Framework.ACTIX)
        except OSError:
            pass

    # Java frameworks — check pom.xml or build.gradle
    for fname in ("pom.xml", "build.gradle", "build.gradle.kts"):
        if fname in file_name_to_path:
            try:
                content = file_name_to_path[fname].read_text()
                if "spring" in content.lower():
                    frameworks.append(Framework.SPRING)
                    break
            except OSError:
                pass

    return frameworks


def _detect_test_runners(
    root: Path, file_names: set[str], file_name_to_path: dict[str, Path],
    all_files: list[Path]
) -> list[TestRunner]:
    """Detect testing frameworks."""
    runners = []

    # Python: pytest, unittest
    has_tests_dir = (root / "tests").is_dir() or (root / "test").is_dir()
    py_test_files = [f for f in all_files if f.name.startswith("test_") and f.suffix == ".py"]

    if "pyproject.toml" in file_name_to_path:
        try:
            content = file_name_to_path["pyproject.toml"].read_text()
            if "pytest" in content:
                runners.append(TestRunner.PYTEST)
        except OSError:
            pass

    if TestRunner.PYTEST not in runners:
        for fname in ("requirements.txt", "requirements-dev.txt", "setup.cfg"):
            if fname in file_name_to_path:
                try:
                    content = file_name_to_path[fname].read_text()
                    if "pytest" in content:
                        runners.append(TestRunner.PYTEST)
                        break
                except OSError:
                    pass

    if TestRunner.PYTEST not in runners and (has_tests_dir or py_test_files):
        # Check if any test files use unittest
        sample = _read_sample_files(root, "test_*.py", max_files=5)
        if any("import unittest" in c or "from unittest" in c for c in sample):
            runners.append(TestRunner.UNITTEST)
        elif py_test_files:
            runners.append(TestRunner.PYTEST)  # default for Python

    # Node: jest, mocha, vitest
    if "package.json" in file_name_to_path:
        try:
            pkg = json.loads(file_name_to_path["package.json"].read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            scripts = pkg.get("scripts", {})
            if "vitest" in deps or "vitest" in scripts.get("test", ""):
                runners.append(TestRunner.VITEST)
            elif "jest" in deps or "jest" in scripts.get("test", ""):
                runners.append(TestRunner.JEST)
            elif "mocha" in deps or "mocha" in scripts.get("test", ""):
                runners.append(TestRunner.MOCHA)
        except (json.JSONDecodeError, OSError):
            pass

    # Go: go test (any _test.go files)
    go_test_files = [f for f in all_files if f.name.endswith("_test.go")]
    if go_test_files:
        runners.append(TestRunner.GO_TEST)

    # Rust: cargo test (any #[test] or #[cfg(test)])
    rs_files = [f for f in all_files if f.suffix == ".rs"]
    for rf in rs_files[:10]:
        try:
            content = rf.read_text()
            if "#[test]" in content or "#[cfg(test)]" in content:
                runners.append(TestRunner.CARGO_TEST)
                break
        except OSError:
            pass

    # Java: JUnit
    java_files = [f for f in all_files if f.suffix == ".java"]
    for jf in java_files[:10]:
        try:
            content = jf.read_text()
            if "@Test" in content or "import org.junit" in content:
                runners.append(TestRunner.JUNIT)
                break
        except OSError:
            pass

    return runners


def _detect_linters(file_names: set[str], file_name_to_path: dict[str, Path]) -> list[Linter]:
    """Detect linters and formatters."""
    linters = []

    # Check pyproject.toml for Python linters
    if "pyproject.toml" in file_name_to_path:
        try:
            content = file_name_to_path["pyproject.toml"].read_text()
            if "[tool.ruff" in content or "ruff" in content:
                linters.append(Linter.RUFF)
            if "[tool.black" in content or "black" in content.split("[tool.ruff")[0] if "[tool.ruff" in content else content:
                linters.append(Linter.BLACK)
            if "mypy" in content:
                linters.append(Linter.MYPY)
            if "flake8" in content:
                linters.append(Linter.FLAKE8)
            if "pylint" in content:
                linters.append(Linter.PYLINT)
        except OSError:
            pass

    # Check config files directly
    config_linter_map = {
        ".flake8": Linter.FLAKE8,
        ".pylintrc": Linter.PYLINT,
        ".eslintrc.js": Linter.ESLINT,
        ".eslintrc.json": Linter.ESLINT,
        ".eslintrc.yml": Linter.ESLINT,
        "eslint.config.js": Linter.ESLINT,
        ".prettierrc": Linter.PRETTIER,
        ".prettierrc.json": Linter.PRETTIER,
        "prettier.config.js": Linter.PRETTIER,
        "rustfmt.toml": Linter.RUSTFMT,
        ".golangci.yml": Linter.GOLANGCI_LINT,
        ".golangci.yaml": Linter.GOLANGCI_LINT,
    }

    for fname, linter in config_linter_map.items():
        if fname in file_names and linter not in linters:
            linters.append(linter)

    # Check requirements files for Python linters
    for fname in ("requirements.txt", "requirements-dev.txt"):
        if fname in file_name_to_path:
            try:
                content = file_name_to_path[fname].read_text().lower()
                if "ruff" in content and Linter.RUFF not in linters:
                    linters.append(Linter.RUFF)
                if "black" in content and Linter.BLACK not in linters:
                    linters.append(Linter.BLACK)
                if "flake8" in content and Linter.FLAKE8 not in linters:
                    linters.append(Linter.FLAKE8)
                if "mypy" in content and Linter.MYPY not in linters:
                    linters.append(Linter.MYPY)
            except OSError:
                pass

    # Rust: clippy is built-in with rustup
    if "Cargo.toml" in file_names:
        if Linter.CLIPPY not in linters:
            linters.append(Linter.CLIPPY)
        if Linter.RUSTFMT not in linters:
            linters.append(Linter.RUSTFMT)

    return linters


def _detect_databases(
    root: Path, file_names: set[str], file_name_to_path: dict[str, Path]
) -> list[DatabaseType]:
    """Detect database usage from config files and code."""
    databases = []

    # Check docker-compose for database services
    for fname in ("docker-compose.yml", "docker-compose.yaml"):
        if fname in file_name_to_path:
            try:
                content = file_name_to_path[fname].read_text().lower()
                if "postgres" in content:
                    databases.append(DatabaseType.POSTGRESQL)
                if "mysql" in content or "mariadb" in content:
                    databases.append(DatabaseType.MYSQL)
                if "mongo" in content:
                    databases.append(DatabaseType.MONGODB)
                if "redis" in content:
                    databases.append(DatabaseType.REDIS)
            except OSError:
                pass

    # Check Python files for database imports
    py_content = _read_sample_files(root, "*.py", max_files=15)
    combined = " ".join(py_content)
    if "psycopg" in combined or "asyncpg" in combined or "postgresql" in combined:
        if DatabaseType.POSTGRESQL not in databases:
            databases.append(DatabaseType.POSTGRESQL)
    if "pymysql" in combined or "mysql" in combined.lower():
        if DatabaseType.MYSQL not in databases:
            databases.append(DatabaseType.MYSQL)
    if "sqlite" in combined:
        if DatabaseType.SQLITE not in databases:
            databases.append(DatabaseType.SQLITE)
    if "pymongo" in combined or "motor" in combined:
        if DatabaseType.MONGODB not in databases:
            databases.append(DatabaseType.MONGODB)
    if "redis" in combined or "aioredis" in combined:
        if DatabaseType.REDIS not in databases:
            databases.append(DatabaseType.REDIS)

    # Check Node package.json for database clients
    if "package.json" in file_name_to_path:
        try:
            pkg = json.loads(file_name_to_path["package.json"].read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "pg" in deps or "sequelize" in deps or "prisma" in deps:
                if DatabaseType.POSTGRESQL not in databases:
                    databases.append(DatabaseType.POSTGRESQL)
            if "mongoose" in deps or "mongodb" in deps:
                if DatabaseType.MONGODB not in databases:
                    databases.append(DatabaseType.MONGODB)
            if "redis" in deps or "ioredis" in deps:
                if DatabaseType.REDIS not in databases:
                    databases.append(DatabaseType.REDIS)
        except (json.JSONDecodeError, OSError):
            pass

    return databases


def _detect_entry_points(file_names: set[str], analysis: ProjectAnalysis) -> list[str]:
    """Detect application entry points."""
    entries = []
    if "main.py" in file_names:
        entries.append("main.py")
    if "app.py" in file_names:
        entries.append("app.py")
    if "manage.py" in file_names:
        entries.append("manage.py")
    if "server.js" in file_names:
        entries.append("server.js")
    if "index.js" in file_names:
        entries.append("index.js")
    if "main.go" in file_names:
        entries.append("main.go")
    if "main.rs" in file_names:
        entries.append("main.rs")
    return entries


def _detect_port(
    root: Path, file_name_to_path: dict[str, Path], analysis: ProjectAnalysis
) -> int | None:
    """Try to detect the application port."""
    # Framework defaults
    framework_ports = {
        Framework.FASTAPI: 8000,
        Framework.DJANGO: 8000,
        Framework.FLASK: 5000,
        Framework.EXPRESS: 3000,
        Framework.NEXTJS: 3000,
        Framework.GIN: 8080,
        Framework.SPRING: 8080,
        Framework.ACTIX: 8080,
    }

    # Check .env for PORT
    for fname in (".env", ".env.example"):
        if fname in file_name_to_path:
            try:
                content = file_name_to_path[fname].read_text()
                match = re.search(r"PORT\s*=\s*(\d+)", content)
                if match:
                    return int(match.group(1))
            except OSError:
                pass

    # Use framework default
    for fw in analysis.frameworks:
        if fw in framework_ports:
            return framework_ports[fw]

    return None


def _read_sample_files(root: Path, pattern: str, max_files: int = 10) -> list[str]:
    """Read content of up to max_files matching a glob pattern."""
    contents = []
    for fpath in root.rglob(pattern):
        if any(skip in fpath.parts for skip in SKIP_DIRS):
            continue
        try:
            text = fpath.read_text(errors="ignore")
            contents.append(text[:5000])  # Limit per file
            if len(contents) >= max_files:
                break
        except OSError:
            pass
    return contents
