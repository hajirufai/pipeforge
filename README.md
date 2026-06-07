# 🔧 PipeForge

**Intelligent CI/CD Pipeline Generator** — Analyze your codebase and generate production-ready CI/CD configurations in seconds.

[![CI](https://github.com/hajirufai/pipeforge/actions/workflows/ci.yml/badge.svg)](https://github.com/hajirufai/pipeforge/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

PipeForge scans your project directory, detects languages, frameworks, test runners, linters, and databases, then generates optimized pipeline configs for **GitHub Actions**, **GitLab CI**, and **Docker** — complete with caching, matrix testing, security scanning, and multi-stage builds.

## ✨ Features

- **Smart Project Analysis** — Detects Python, JavaScript/TypeScript, Go, Rust, and Java ecosystems
- **GitHub Actions** — CI workflows with dependency caching, matrix testing, linting, coverage, and CodeQL security scanning
- **GitLab CI** — Stage-based pipelines with service containers and Docker-in-Docker builds
- **Docker** — Optimized multi-stage Dockerfiles, `.dockerignore`, and `docker-compose.yml` with database services
- **Config Validation** — Validate existing workflow files for errors and best practice violations
- **Rich CLI** — Beautiful terminal output with progress indicators and tree views

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

Or install as a package:

```bash
pip install -e .
```

### Generate Pipelines

```bash
# Analyze and generate GitHub Actions CI for current directory
pipeforge generate .

# Generate for a specific project
pipeforge generate /path/to/your/project

# Generate multiple platforms
pipeforge generate . -p github_actions -p gitlab_ci -p docker

# Include deployment workflow
pipeforge generate . --deploy --deploy-provider vercel

# Preview without writing files
pipeforge generate . --dry-run
```

### Analyze a Project

```bash
# Rich table output
pipeforge analyze /path/to/project

# JSON output
pipeforge inspect /path/to/project
```

### Validate Configs

```bash
# Validate a GitHub Actions workflow
pipeforge validate .github/workflows/ci.yml

# Validate a Dockerfile
pipeforge validate Dockerfile

# Validate a GitLab CI config
pipeforge validate .gitlab-ci.yml
```

## 📊 Example Output

### Analysis

```
┌──────────────────── Project Analysis ─────────────────────┐
│ Category         │ Detected                                │
├──────────────────┼─────────────────────────────────────────┤
│ Languages        │ python (12 files)*                      │
│ Frameworks       │ fastapi                                 │
│ Package Managers │ pip                                     │
│ Test Runners     │ pytest                                  │
│ Linters          │ ruff, mypy                              │
│ Databases        │ postgresql, redis                       │
│ Docker           │ ✅ Found                                │
│ Port             │ 8000                                    │
└──────────────────┴─────────────────────────────────────────┘
```

### Generated GitHub Actions CI

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: --health-cmd pg_isready ...
      redis:
        image: redis:7
        ports:
          - 6379:6379
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-...
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Lint with Ruff
        run: ruff check .
      - name: Type check with MyPy
        run: mypy .
      - name: Run tests
        run: pytest --tb=short --cov --cov-report=term-missing
```

## 🔍 Supported Detections

| Category | Detected Items |
|----------|---------------|
| **Languages** | Python, JavaScript, TypeScript, Go, Rust, Java |
| **Frameworks** | FastAPI, Django, Flask, Express, Next.js, Gin, Spring, Actix |
| **Package Managers** | pip, Poetry, Pipenv, npm, Yarn, pnpm, Cargo, Go Modules, Maven, Gradle |
| **Test Runners** | pytest, unittest, Jest, Mocha, Vitest, go test, cargo test, JUnit |
| **Linters** | Ruff, Black, Flake8, Pylint, MyPy, ESLint, Prettier, golangci-lint, Clippy, rustfmt |
| **Databases** | PostgreSQL, MySQL, SQLite, MongoDB, Redis |

## 🏗️ Architecture

```
pipeforge/
├── analyzer.py           # Project scanning & detection engine
├── models.py             # Data models (ProjectAnalysis, GeneratorConfig)
├── generators/
│   ├── base.py           # Abstract base with Jinja2 template support
│   ├── github_actions.py # GitHub Actions workflow generator
│   ├── gitlab_ci.py      # GitLab CI config generator
│   └── docker.py         # Dockerfile + compose generator
├── validator.py          # YAML, workflow, and Dockerfile validation
└── cli.py                # Rich CLI (click + rich)
```

### Design Principles

1. **Analyzer-Generator Pattern** — Analysis and generation are decoupled; add new generators without touching the analyzer
2. **Best Practices Built-In** — Every generated config follows platform-specific best practices (caching, security, multi-stage builds)
3. **Non-Destructive** — Won't overwrite existing files without confirmation; dry-run mode available
4. **Extensible** — Template-based generation with Jinja2; easy to add new platforms or customize output

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=pipeforge --cov-report=term-missing

# Run specific test suite
pytest tests/test_analyzer.py -v
```

116 tests covering analysis, generation, validation, and CLI.

## 📝 CLI Reference

| Command | Description |
|---------|-------------|
| `pipeforge analyze [PATH]` | Analyze a project and display detection results |
| `pipeforge generate [PATH]` | Generate CI/CD pipeline configurations |
| `pipeforge validate FILE` | Validate an existing CI/CD config file |
| `pipeforge inspect [PATH]` | Output analysis results as JSON |
| `pipeforge --version` | Show version |

### Generate Options

| Flag | Description |
|------|-------------|
| `-p, --platform` | Target platform: `github_actions`, `gitlab_ci`, `docker` (repeatable) |
| `--security / --no-security` | Include CodeQL security scanning (default: on) |
| `--deploy` | Include deployment workflow |
| `--deploy-provider` | Deployment provider: `vercel`, `heroku`, `generic` |
| `-o, --output` | Output directory (default: project directory) |
| `--dry-run` | Preview generated files without writing |
| `--force` | Overwrite existing files without asking |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 👤 Author

**Haji Rufai** — [GitHub](https://github.com/hajirufai) · [LinkedIn](https://www.linkedin.com/in/hajirufai/) · [dev.to](https://dev.to/hajirufai)
