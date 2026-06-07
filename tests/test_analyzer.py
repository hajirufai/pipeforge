"""Tests for the project analyzer."""

import json
from pathlib import Path

from pipeforge.analyzer import analyze_project
from pipeforge.models import (
    DatabaseType,
    Framework,
    Language,
    Linter,
    PackageManager,
    TestRunner,
)


class TestLanguageDetection:
    def test_python_detection(self, python_project):
        result = analyze_project(str(python_project.root))
        langs = [li.language for li in result.languages]
        assert Language.PYTHON in langs

    def test_python_is_primary(self, python_project):
        result = analyze_project(str(python_project.root))
        primary = [li for li in result.languages if li.is_primary]
        assert len(primary) == 1
        assert primary[0].language == Language.PYTHON

    def test_node_detection(self, node_project):
        result = analyze_project(str(node_project.root))
        langs = [li.language for li in result.languages]
        assert Language.JAVASCRIPT in langs or Language.TYPESCRIPT in langs

    def test_go_detection(self, go_project):
        result = analyze_project(str(go_project.root))
        langs = [li.language for li in result.languages]
        assert Language.GO in langs

    def test_rust_detection(self, tmp_project):
        tmp_project.add_rust_project()
        result = analyze_project(str(tmp_project.root))
        langs = [li.language for li in result.languages]
        assert Language.RUST in langs

    def test_java_detection(self, tmp_project):
        tmp_project.add_java_project()
        result = analyze_project(str(tmp_project.root))
        langs = [li.language for li in result.languages]
        assert Language.JAVA in langs

    def test_file_counts(self, python_project):
        result = analyze_project(str(python_project.root))
        py_info = next(li for li in result.languages if li.language == Language.PYTHON)
        assert py_info.file_count >= 4  # main.py, __init__.py, routes.py, test_app.py

    def test_empty_directory(self, tmp_path):
        result = analyze_project(str(tmp_path))
        assert result.languages == []
        assert result.primary_language is None

    def test_invalid_path(self):
        import pytest
        with pytest.raises(ValueError):
            analyze_project("/nonexistent/path")


class TestFrameworkDetection:
    def test_fastapi(self, python_project):
        result = analyze_project(str(python_project.root))
        assert Framework.FASTAPI in result.frameworks

    def test_express(self, node_project):
        result = analyze_project(str(node_project.root))
        assert Framework.EXPRESS in result.frameworks

    def test_gin(self, go_project):
        result = analyze_project(str(go_project.root))
        assert Framework.GIN in result.frameworks

    def test_django(self, tmp_project):
        tmp_project.add_file("manage.py", "#!/usr/bin/env python\nimport django\n")
        tmp_project.add_file("requirements.txt", "django>=4.0\n")
        result = analyze_project(str(tmp_project.root))
        assert Framework.DJANGO in result.frameworks

    def test_flask(self, tmp_project):
        tmp_project.add_file("app.py", "from flask import Flask\napp = Flask(__name__)\n")
        result = analyze_project(str(tmp_project.root))
        assert Framework.FLASK in result.frameworks

    def test_nextjs(self, tmp_project):
        pkg = {"dependencies": {"next": "^14.0", "react": "^18.0"}}
        tmp_project.add_file("package.json", json.dumps(pkg))
        tmp_project.add_file("pages/index.tsx", "export default function Home() {}\n")
        result = analyze_project(str(tmp_project.root))
        assert Framework.NEXTJS in result.frameworks

    def test_actix(self, tmp_project):
        tmp_project.add_file("Cargo.toml", '[dependencies]\nactix-web = "4"\n')
        tmp_project.add_file("src/main.rs", "fn main() {}\n")
        result = analyze_project(str(tmp_project.root))
        assert Framework.ACTIX in result.frameworks

    def test_spring(self, tmp_project):
        tmp_project.add_java_project()
        result = analyze_project(str(tmp_project.root))
        assert Framework.SPRING in result.frameworks


class TestPackageManagerDetection:
    def test_pip(self, tmp_project):
        tmp_project.add_file("requirements.txt", "flask>=2.0\n")
        result = analyze_project(str(tmp_project.root))
        assert PackageManager.PIP in result.package_managers

    def test_poetry(self, tmp_project):
        tmp_project.add_file("pyproject.toml", "[tool.poetry]\nname = 'test'\n")
        result = analyze_project(str(tmp_project.root))
        assert PackageManager.POETRY in result.package_managers

    def test_npm(self, node_project):
        result = analyze_project(str(node_project.root))
        assert PackageManager.NPM in result.package_managers

    def test_yarn(self, tmp_project):
        tmp_project.add_file("package.json", '{"name": "test"}')
        tmp_project.add_file("yarn.lock", "")
        result = analyze_project(str(tmp_project.root))
        assert PackageManager.YARN in result.package_managers

    def test_cargo(self, tmp_project):
        tmp_project.add_rust_project()
        result = analyze_project(str(tmp_project.root))
        assert PackageManager.CARGO in result.package_managers

    def test_go_mod(self, go_project):
        result = analyze_project(str(go_project.root))
        assert PackageManager.GO_MOD in result.package_managers


class TestTestRunnerDetection:
    def test_pytest(self, python_project):
        result = analyze_project(str(python_project.root))
        assert TestRunner.PYTEST in result.test_runners

    def test_jest(self, node_project):
        result = analyze_project(str(node_project.root))
        assert TestRunner.JEST in result.test_runners

    def test_go_test(self, go_project):
        result = analyze_project(str(go_project.root))
        assert TestRunner.GO_TEST in result.test_runners

    def test_cargo_test(self, tmp_project):
        tmp_project.add_rust_project()
        result = analyze_project(str(tmp_project.root))
        assert TestRunner.CARGO_TEST in result.test_runners

    def test_junit(self, tmp_project):
        tmp_project.add_java_project()
        result = analyze_project(str(tmp_project.root))
        assert TestRunner.JUNIT in result.test_runners


class TestLinterDetection:
    def test_ruff_from_pyproject(self, python_project):
        result = analyze_project(str(python_project.root))
        assert Linter.RUFF in result.linters

    def test_flake8_from_config(self, python_project):
        result = analyze_project(str(python_project.root))
        assert Linter.FLAKE8 in result.linters

    def test_eslint(self, node_project):
        result = analyze_project(str(node_project.root))
        assert Linter.ESLINT in result.linters

    def test_prettier(self, node_project):
        result = analyze_project(str(node_project.root))
        assert Linter.PRETTIER in result.linters

    def test_golangci_lint(self, go_project):
        result = analyze_project(str(go_project.root))
        assert Linter.GOLANGCI_LINT in result.linters

    def test_clippy_auto(self, tmp_project):
        tmp_project.add_rust_project()
        result = analyze_project(str(tmp_project.root))
        assert Linter.CLIPPY in result.linters


class TestDatabaseDetection:
    def test_postgres_from_docker_compose(self, python_project):
        python_project.add_docker()
        result = analyze_project(str(python_project.root))
        assert DatabaseType.POSTGRESQL in result.databases

    def test_sqlite_from_imports(self, tmp_project):
        tmp_project.add_file("app.py", "import sqlite3\nconn = sqlite3.connect('db.sqlite3')\n")
        result = analyze_project(str(tmp_project.root))
        assert DatabaseType.SQLITE in result.databases

    def test_mongodb_from_package_json(self, tmp_project):
        pkg = {"dependencies": {"mongoose": "^7.0"}}
        tmp_project.add_file("package.json", json.dumps(pkg))
        result = analyze_project(str(tmp_project.root))
        assert DatabaseType.MONGODB in result.databases


class TestMiscDetection:
    def test_docker_detected(self, python_project):
        python_project.add_docker()
        result = analyze_project(str(python_project.root))
        assert result.has_docker is True

    def test_no_docker(self, python_project):
        result = analyze_project(str(python_project.root))
        assert result.has_docker is False

    def test_ci_detected(self, python_project):
        python_project.add_ci()
        result = analyze_project(str(python_project.root))
        assert result.has_ci is True

    def test_entry_points(self, python_project):
        result = analyze_project(str(python_project.root))
        assert "main.py" in result.entry_points

    def test_port_detection_fastapi(self, python_project):
        result = analyze_project(str(python_project.root))
        assert result.port == 8000

    def test_port_from_env(self, tmp_project):
        tmp_project.add_file(".env", "PORT=3333\nDEBUG=true\n")
        tmp_project.add_file("app.py", "print('hello')\n")
        result = analyze_project(str(tmp_project.root))
        assert result.port == 3333

    def test_project_name(self, python_project):
        result = analyze_project(str(python_project.root))
        assert result.project_name is not None

    def test_to_dict(self, python_project):
        result = analyze_project(str(python_project.root))
        d = result.to_dict()
        assert "languages" in d
        assert "frameworks" in d
        assert "project_name" in d
