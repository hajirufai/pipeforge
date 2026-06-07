"""Shared test fixtures for PipeForge tests."""

import json
import os
import tempfile

import pytest


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with helpers."""

    class ProjectBuilder:
        def __init__(self, root):
            self.root = root

        def add_file(self, path, content=""):
            fpath = self.root / path
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content)
            return fpath

        def add_python_project(self):
            """Create a basic Python project structure."""
            self.add_file("requirements.txt", "fastapi>=0.100\nuvicorn>=0.23\npytest>=7.0\n")
            self.add_file("main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
            self.add_file("app/__init__.py", "")
            self.add_file("app/routes.py", "from fastapi import APIRouter\nrouter = APIRouter()\n")
            self.add_file("tests/__init__.py", "")
            self.add_file("tests/test_app.py", "def test_health():\n    assert True\n")
            self.add_file("pyproject.toml", '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n[tool.ruff]\nline-length = 88\n')
            self.add_file(".flake8", "[flake8]\nmax-line-length = 88\n")
            return self

        def add_node_project(self):
            """Create a basic Node.js project structure."""
            pkg = {
                "name": "test-app",
                "version": "1.0.0",
                "scripts": {"test": "jest", "build": "tsc"},
                "dependencies": {"express": "^4.18"},
                "devDependencies": {"jest": "^29.0", "eslint": "^8.0", "prettier": "^3.0"},
            }
            self.add_file("package.json", json.dumps(pkg, indent=2))
            self.add_file("index.js", "const express = require('express');\n")
            self.add_file("src/app.ts", "import express from 'express';\n")
            self.add_file("tsconfig.json", '{"compilerOptions": {"target": "es2020"}}')
            self.add_file(".eslintrc.json", '{"extends": "eslint:recommended"}')
            self.add_file(".prettierrc", '{"semi": true}')
            return self

        def add_go_project(self):
            """Create a basic Go project structure."""
            self.add_file("go.mod", "module example.com/myapp\n\ngo 1.22\n\nrequire github.com/gin-gonic/gin v1.9.1\n")
            self.add_file("main.go", 'package main\n\nfunc main() {}\n')
            self.add_file("handler/handler.go", "package handler\n")
            self.add_file("handler/handler_test.go", "package handler\n\nimport \"testing\"\n\nfunc TestHandler(t *testing.T) {}\n")
            self.add_file(".golangci.yml", "linters:\n  enable:\n    - gofmt\n")
            return self

        def add_rust_project(self):
            """Create a basic Rust project structure."""
            self.add_file("Cargo.toml", '[package]\nname = "myapp"\nversion = "0.1.0"\n\n[dependencies]\nactix-web = "4"\n')
            self.add_file("src/main.rs", 'fn main() {\n    println!("Hello");\n}\n\n#[test]\nfn it_works() { assert!(true); }\n')
            self.add_file("rustfmt.toml", "max_width = 100\n")
            return self

        def add_java_project(self):
            """Create a basic Java/Maven project."""
            self.add_file("pom.xml", '<project>\n<groupId>com.example</groupId>\n<artifactId>myapp</artifactId>\n<dependencies><dependency><groupId>org.springframework.boot</groupId></dependency></dependencies>\n</project>\n')
            self.add_file("src/main/java/App.java", "public class App { public static void main(String[] args) {} }\n")
            self.add_file("src/test/java/AppTest.java", "import org.junit.Test;\npublic class AppTest { @Test public void test() {} }\n")
            return self

        def add_docker(self):
            """Add Docker files."""
            self.add_file("Dockerfile", "FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\nCMD [\"python\", \"main.py\"]\n")
            self.add_file("docker-compose.yml", "services:\n  app:\n    build: .\n    ports:\n      - '8000:8000'\n  postgres:\n    image: postgres:16\n")
            return self

        def add_ci(self):
            """Add existing CI config."""
            self.add_file(".github/workflows/ci.yml", "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n")
            return self

    return ProjectBuilder(tmp_path)


@pytest.fixture
def python_project(tmp_project):
    """A ready-to-analyze Python project."""
    return tmp_project.add_python_project()


@pytest.fixture
def node_project(tmp_project):
    """A ready-to-analyze Node.js project."""
    return tmp_project.add_node_project()


@pytest.fixture
def go_project(tmp_project):
    """A ready-to-analyze Go project."""
    return tmp_project.add_go_project()
