"""Abstract base class for pipeline generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..models import GeneratedFile, GeneratorConfig, ProjectAnalysis

# Templates directory
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class BaseGenerator(ABC):
    """Base class for all pipeline generators."""

    def __init__(self, analysis: ProjectAnalysis, config: GeneratorConfig):
        self.analysis = analysis
        self.config = config
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render_template(self, template_path: str, **context) -> str:
        """Render a Jinja2 template with the given context."""
        template = self._env.get_template(template_path)
        return template.render(analysis=self.analysis, config=self.config, **context)

    @abstractmethod
    def generate(self) -> list[GeneratedFile]:
        """Generate pipeline configuration files.

        Returns:
            List of GeneratedFile objects.
        """
        ...

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform name."""
        ...
