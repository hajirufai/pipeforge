"""Docker configuration generator (Dockerfile, .dockerignore, docker-compose)."""

from __future__ import annotations

from ..models import (
    DatabaseType,
    Framework,
    GeneratedFile,
    Language,
    PackageManager,
)
from .base import BaseGenerator


class DockerGenerator(BaseGenerator):
    """Generates Docker-related configuration files."""

    platform_name = "Docker"

    def generate(self) -> list[GeneratedFile]:
        files = []
        files.append(self._generate_dockerfile())
        files.append(self._generate_dockerignore())
        if self.analysis.databases or self.analysis.frameworks:
            files.append(self._generate_docker_compose())
        return files

    def _generate_dockerfile(self) -> GeneratedFile:
        lang = self.analysis.primary_language

        if lang == Language.PYTHON:
            content = self._python_dockerfile()
        elif lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            content = self._node_dockerfile()
        elif lang == Language.GO:
            content = self._go_dockerfile()
        elif lang == Language.RUST:
            content = self._rust_dockerfile()
        elif lang == Language.JAVA:
            content = self._java_dockerfile()
        else:
            content = self._generic_dockerfile()

        return GeneratedFile(
            path="Dockerfile",
            content=content,
            description="Multi-stage Dockerfile optimized for production",
            overwrite_warning=True,
        )

    def _python_dockerfile(self) -> str:
        has_poetry = PackageManager.POETRY in self.analysis.package_managers
        port = self.analysis.port or 8000
        entry = self.analysis.entry_points[0] if self.analysis.entry_points else "main.py"

        # Determine the run command
        if Framework.FASTAPI in self.analysis.frameworks:
            run_cmd = f'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{port}"]'
        elif Framework.DJANGO in self.analysis.frameworks:
            run_cmd = f'CMD ["gunicorn", "--bind", "0.0.0.0:{port}", "--workers", "4", "config.wsgi:application"]'
        elif Framework.FLASK in self.analysis.frameworks:
            run_cmd = f'CMD ["gunicorn", "--bind", "0.0.0.0:{port}", "--workers", "4", "app:app"]'
        else:
            run_cmd = f'CMD ["python", "{entry}"]'

        if has_poetry:
            return f"""# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.3 \\
    && poetry config virtualenvs.in-project true

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev deps for production)
RUN poetry install --no-interaction --no-ansi --without dev

# Stage 2: Production
FROM python:3.12-slim AS production

WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

EXPOSE {port}

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{port}/health')" || exit 1

{run_cmd}
"""
        else:
            return f"""# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production
FROM python:3.12-slim AS production

WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

EXPOSE {port}

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{port}/health')" || exit 1

{run_cmd}
"""

    def _node_dockerfile(self) -> str:
        has_yarn = PackageManager.YARN in self.analysis.package_managers
        has_pnpm = PackageManager.PNPM in self.analysis.package_managers
        is_nextjs = Framework.NEXTJS in self.analysis.frameworks
        port = self.analysis.port or 3000

        if has_pnpm:
            install_cmd = "RUN npm install -g pnpm && pnpm install --frozen-lockfile"
            prod_install = "RUN npm install -g pnpm && pnpm install --frozen-lockfile --prod"
            copy_lock = "COPY pnpm-lock.yaml* ./"
        elif has_yarn:
            install_cmd = "RUN yarn install --frozen-lockfile"
            prod_install = "RUN yarn install --frozen-lockfile --production"
            copy_lock = "COPY yarn.lock* ./"
        else:
            install_cmd = "RUN npm ci"
            prod_install = "RUN npm ci --only=production"
            copy_lock = "COPY package-lock.json* ./"

        if is_nextjs:
            return f"""# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json {copy_lock.split("COPY ")[1].split(" ./")[0]} ./
{install_cmd}

# Stage 2: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Stage 3: Production
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE {port}
ENV PORT={port}

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost:{port}/ || exit 1

CMD ["node", "server.js"]
"""
        else:
            entry = self.analysis.entry_points[0] if self.analysis.entry_points else "index.js"
            return f"""# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json {copy_lock.split("COPY ")[1].split(" ./")[0]} ./
{install_cmd}
COPY . .

# Stage 2: Production
FROM node:20-alpine AS production
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 appgroup
RUN adduser --system --uid 1001 appuser

COPY package.json {copy_lock.split("COPY ")[1].split(" ./")[0]} ./
{prod_install}
COPY --from=builder /app .

USER appuser

EXPOSE {port}

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost:{port}/ || exit 1

CMD ["node", "{entry}"]
"""

    def _go_dockerfile(self) -> str:
        port = self.analysis.port or 8080
        return f"""# Stage 1: Build
FROM golang:1.22-alpine AS builder

WORKDIR /app

# Download dependencies first (layer caching)
COPY go.mod go.sum* ./
RUN go mod download

# Copy source and build
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app/server ./...

# Stage 2: Production (distroless for minimal attack surface)
FROM gcr.io/distroless/static-debian12 AS production

COPY --from=builder /app/server /server

EXPOSE {port}

USER nonroot:nonroot

ENTRYPOINT ["/server"]
"""

    def _rust_dockerfile(self) -> str:
        port = self.analysis.port or 8080
        return f"""# Stage 1: Build
FROM rust:1.77-slim AS builder

WORKDIR /app

# Cache dependencies
COPY Cargo.toml Cargo.lock* ./
RUN mkdir src && echo "fn main() {{}}" > src/main.rs
RUN cargo build --release && rm -rf src

# Build actual application
COPY . .
RUN touch src/main.rs && cargo build --release

# Stage 2: Production
FROM debian:bookworm-slim AS production

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /app/target/release/app /usr/local/bin/app

USER appuser

EXPOSE {port}

ENTRYPOINT ["app"]
"""

    def _java_dockerfile(self) -> str:
        has_gradle = PackageManager.GRADLE in self.analysis.package_managers
        port = self.analysis.port or 8080

        if has_gradle:
            build_cmd = "./gradlew build -x test"
            jar_path = "build/libs/*.jar"
        else:
            build_cmd = "mvn package -DskipTests"
            jar_path = "target/*.jar"

        return f"""# Stage 1: Build
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /app
COPY . .
RUN {build_cmd}

# Stage 2: Production
FROM eclipse-temurin:21-jre-alpine AS production

WORKDIR /app

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=builder /app/{jar_path} app.jar

USER appuser

EXPOSE {port}

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost:{port}/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
"""

    def _generic_dockerfile(self) -> str:
        return """FROM ubuntu:22.04

WORKDIR /app

COPY . .

# Add your build commands here
RUN echo "Configure your build steps"

CMD ["echo", "Configure your start command"]
"""

    def _generate_dockerignore(self) -> GeneratedFile:
        lang = self.analysis.primary_language
        ignore_lines = [
            "# Version control",
            ".git",
            ".gitignore",
            "",
            "# CI/CD",
            ".github",
            ".gitlab-ci.yml",
            "",
            "# IDE",
            ".vscode",
            ".idea",
            "*.swp",
            "*.swo",
            "",
            "# Documentation",
            "*.md",
            "LICENSE",
            "docs/",
            "",
            "# Docker",
            "Dockerfile*",
            "docker-compose*",
            ".dockerignore",
            "",
        ]

        if lang == Language.PYTHON:
            ignore_lines += [
                "# Python",
                "__pycache__",
                "*.pyc",
                "*.pyo",
                ".venv",
                "venv",
                ".env",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                "*.egg-info",
                "dist",
                "build",
                "htmlcov",
                ".coverage",
            ]
        elif lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            ignore_lines += [
                "# Node",
                "node_modules",
                ".next",
                ".nuxt",
                "dist",
                "build",
                "coverage",
                ".env",
                ".env.local",
                "*.log",
            ]
        elif lang == Language.GO:
            ignore_lines += [
                "# Go",
                "vendor/",
                "*.test",
                "coverage.out",
            ]
        elif lang == Language.RUST:
            ignore_lines += [
                "# Rust",
                "target/",
                "*.rs.bk",
            ]

        return GeneratedFile(
            path=".dockerignore",
            content="\n".join(ignore_lines) + "\n",
            description="Docker ignore file to reduce build context size",
        )

    def _generate_docker_compose(self) -> GeneratedFile:
        services = {}
        lang = self.analysis.primary_language
        port = self.analysis.port or 8000

        # Main app service
        app_service = {
            "build": ".",
            "ports": [f"{port}:{port}"],
            "environment": [],
            "depends_on": {},
            "restart": "unless-stopped",
        }

        # Database services
        if DatabaseType.POSTGRESQL in self.analysis.databases:
            services["postgres"] = {
                "image": "postgres:16-alpine",
                "environment": [
                    "POSTGRES_USER=app",
                    "POSTGRES_PASSWORD=secret",
                    "POSTGRES_DB=appdb",
                ],
                "ports": ["5432:5432"],
                "volumes": ["postgres_data:/var/lib/postgresql/data"],
                "healthcheck": {
                    "test": ["CMD-SHELL", "pg_isready -U app"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                },
            }
            app_service["depends_on"]["postgres"] = {"condition": "service_healthy"}
            app_service["environment"].append("DATABASE_URL=postgresql://app:secret@postgres:5432/appdb")

        if DatabaseType.REDIS in self.analysis.databases:
            services["redis"] = {
                "image": "redis:7-alpine",
                "ports": ["6379:6379"],
                "healthcheck": {
                    "test": ["CMD", "redis-cli", "ping"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                },
            }
            app_service["depends_on"]["redis"] = {"condition": "service_healthy"}
            app_service["environment"].append("REDIS_URL=redis://redis:6379")

        if DatabaseType.MONGODB in self.analysis.databases:
            services["mongodb"] = {
                "image": "mongo:7",
                "ports": ["27017:27017"],
                "environment": [
                    "MONGO_INITDB_ROOT_USERNAME=app",
                    "MONGO_INITDB_ROOT_PASSWORD=secret",
                ],
                "volumes": ["mongo_data:/data/db"],
            }
            app_service["depends_on"]["mongodb"] = {"condition": "service_started"}
            app_service["environment"].append("MONGODB_URL=mongodb://app:secret@mongodb:27017")

        services["app"] = app_service

        # Build YAML manually for clean output
        lines = ["services:"]
        for name, svc in services.items():
            lines.append(f"  {name}:")
            if "build" in svc:
                lines.append(f"    build: {svc['build']}")
            if "image" in svc:
                lines.append(f"    image: {svc['image']}")
            if svc.get("ports"):
                lines.append("    ports:")
                for p in svc["ports"]:
                    lines.append(f"      - \"{p}\"")
            if svc.get("environment"):
                lines.append("    environment:")
                for env in svc["environment"]:
                    lines.append(f"      - {env}")
            if svc.get("volumes"):
                lines.append("    volumes:")
                for vol in svc["volumes"]:
                    lines.append(f"      - {vol}")
            if svc.get("depends_on"):
                lines.append("    depends_on:")
                for dep, cond in svc["depends_on"].items():
                    lines.append(f"      {dep}:")
                    if isinstance(cond, dict):
                        for k, v in cond.items():
                            lines.append(f"        {k}: {v}")
            if svc.get("restart"):
                lines.append(f"    restart: {svc['restart']}")
            if svc.get("healthcheck"):
                hc = svc["healthcheck"]
                lines.append("    healthcheck:")
                lines.append(f"      test: {hc['test']}")
                lines.append(f"      interval: {hc['interval']}")
                lines.append(f"      timeout: {hc['timeout']}")
                lines.append(f"      retries: {hc['retries']}")
            lines.append("")

        # Volumes
        volumes = []
        if DatabaseType.POSTGRESQL in self.analysis.databases:
            volumes.append("postgres_data")
        if DatabaseType.MONGODB in self.analysis.databases:
            volumes.append("mongo_data")
        if volumes:
            lines.append("volumes:")
            for vol in volumes:
                lines.append(f"  {vol}:")

        return GeneratedFile(
            path="docker-compose.yml",
            content="\n".join(lines) + "\n",
            description="Docker Compose for local development with database services",
            overwrite_warning=True,
        )
