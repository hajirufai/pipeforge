"""Tests for the Docker generator."""

from pipeforge.analyzer import analyze_project
from pipeforge.generators.docker import DockerGenerator
from pipeforge.models import GeneratorConfig


class TestDockerGenerator:
    def test_generates_dockerfile(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        files = gen.generate()

        dockerfile = next(f for f in files if f.path == "Dockerfile")
        assert "FROM" in dockerfile.content
        assert "WORKDIR" in dockerfile.content

    def test_generates_dockerignore(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        files = gen.generate()

        ignore = next(f for f in files if f.path == ".dockerignore")
        assert ".git" in ignore.content
        assert "__pycache__" in ignore.content

    def test_python_multi_stage(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        files = gen.generate()

        dockerfile = next(f for f in files if f.path == "Dockerfile")
        assert dockerfile.content.count("FROM") >= 2  # Multi-stage

    def test_python_non_root_user(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        files = gen.generate()

        dockerfile = next(f for f in files if f.path == "Dockerfile")
        assert "USER" in dockerfile.content
        assert "appuser" in dockerfile.content

    def test_python_healthcheck(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        files = gen.generate()

        dockerfile = next(f for f in files if f.path == "Dockerfile")
        assert "HEALTHCHECK" in dockerfile.content

    def test_node_dockerfile(self, node_project):
        analysis = analyze_project(str(node_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        files = gen.generate()

        dockerfile = next(f for f in files if f.path == "Dockerfile")
        assert "node:" in dockerfile.content
        assert "npm ci" in dockerfile.content or "npm install" in dockerfile.content

    def test_go_distroless(self, go_project):
        analysis = analyze_project(str(go_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        files = gen.generate()

        dockerfile = next(f for f in files if f.path == "Dockerfile")
        assert "distroless" in dockerfile.content or "scratch" in dockerfile.content or "alpine" in dockerfile.content

    def test_docker_compose_with_db(self, python_project):
        python_project.add_docker()
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        files = gen.generate()

        compose = next((f for f in files if f.path == "docker-compose.yml"), None)
        assert compose is not None
        assert "postgres" in compose.content

    def test_dockerfile_overwrite_warning(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        files = gen.generate()

        dockerfile = next(f for f in files if f.path == "Dockerfile")
        assert dockerfile.overwrite_warning is True

    def test_platform_name(self, python_project):
        analysis = analyze_project(str(python_project.root))
        config = GeneratorConfig()
        gen = DockerGenerator(analysis, config)
        assert gen.platform_name == "Docker"
