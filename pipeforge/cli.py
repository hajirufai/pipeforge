"""PipeForge CLI — Generate CI/CD pipelines from your codebase."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from . import __version__
from .analyzer import analyze_project
from .generators import DockerGenerator, GitHubActionsGenerator, GitLabCIGenerator
from .models import GeneratedFile, GeneratorConfig, ProjectAnalysis
from .validator import (
    validate_dockerfile,
    validate_github_actions,
    validate_gitlab_ci,
)

console = Console()

PLATFORM_GENERATORS = {
    "github_actions": GitHubActionsGenerator,
    "gitlab_ci": GitLabCIGenerator,
    "docker": DockerGenerator,
}


@click.group()
@click.version_option(__version__, prog_name="pipeforge")
def cli():
    """🔧 PipeForge — Intelligent CI/CD Pipeline Generator.

    Analyze your codebase and generate production-ready CI/CD configs
    for GitHub Actions, GitLab CI, and Docker.
    """
    pass


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def analyze(path: str):
    """Analyze a project directory and show detection results."""
    console.print(f"\n[bold blue]🔍 Analyzing[/bold blue] {os.path.abspath(path)}\n")

    try:
        result = analyze_project(path)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    _display_analysis(result)


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--platform", "-p", multiple=True, default=["github_actions"],
              type=click.Choice(["github_actions", "gitlab_ci", "docker"]),
              help="Target platform(s)")
@click.option("--security/--no-security", default=True, help="Include security scanning")
@click.option("--deploy", is_flag=True, help="Include deployment workflow")
@click.option("--deploy-provider", type=click.Choice(["vercel", "heroku", "generic"]),
              default="generic", help="Deployment provider")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output directory (default: project directory)")
@click.option("--dry-run", is_flag=True, help="Preview without writing files")
@click.option("--force", is_flag=True, help="Overwrite existing files without asking")
def generate(path: str, platform: tuple, security: bool, deploy: bool,
             deploy_provider: str, output: str, dry_run: bool, force: bool):
    """Generate CI/CD pipeline configs for a project."""
    console.print(f"\n[bold blue]🔧 PipeForge[/bold blue] v{__version__}\n")

    # Analyze
    console.print(f"[dim]Analyzing {os.path.abspath(path)}...[/dim]")
    try:
        analysis = analyze_project(path)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    _display_analysis(analysis)

    if not analysis.languages:
        console.print("[yellow]⚠ No supported languages detected. Nothing to generate.[/yellow]")
        sys.exit(0)

    # Configure
    config = GeneratorConfig(
        platforms=list(platform),
        include_docker="docker" in platform,
        include_security=security,
        include_deploy=deploy,
        deploy_provider=deploy_provider,
        output_dir=output,
    )

    # Generate
    all_files: list[GeneratedFile] = []
    for plat in platform:
        gen_class = PLATFORM_GENERATORS.get(plat)
        if gen_class:
            generator = gen_class(analysis, config)
            console.print(f"\n[bold green]⚡ Generating[/bold green] {generator.platform_name} configs...")
            files = generator.generate()
            all_files.extend(files)

    if not all_files:
        console.print("[yellow]No files generated.[/yellow]")
        sys.exit(0)

    # Display generated files
    output_dir = Path(output or path).resolve()

    tree = Tree(f"📁 [bold]{output_dir.name}[/bold]")
    for gf in all_files:
        icon = "🔒" if gf.overwrite_warning else "📄"
        tree.add(f"{icon} [green]{gf.path}[/green] — {gf.description}")

    console.print("\n[bold]Generated files:[/bold]")
    console.print(tree)

    if dry_run:
        console.print("\n[yellow]Dry run — no files written.[/yellow]")
        for gf in all_files:
            console.print(f"\n[bold]── {gf.path} ──[/bold]")
            console.print(gf.content)
        return

    # Write files
    written = 0
    skipped = 0
    for gf in all_files:
        target = output_dir / gf.path
        if target.exists() and not force:
            if gf.overwrite_warning:
                if not click.confirm(f"  ⚠ {gf.path} exists. Overwrite?"):
                    skipped += 1
                    continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(gf.content)
        written += 1
        console.print(f"  ✅ {gf.path}")

    console.print(f"\n[bold green]Done![/bold green] {written} files written, {skipped} skipped.")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
def validate(file: str):
    """Validate a CI/CD configuration file."""
    console.print(f"\n[bold blue]🔍 Validating[/bold blue] {file}\n")

    content = Path(file).read_text()
    fname = Path(file).name

    # Pick the right validator
    if fname.endswith(".yml") or fname.endswith(".yaml"):
        if ".github" in str(Path(file).resolve()):
            result = validate_github_actions(content, file)
            validator_name = "GitHub Actions"
        elif "gitlab" in fname:
            result = validate_gitlab_ci(content, file)
            validator_name = "GitLab CI"
        else:
            from .validator import validate_yaml
            result = validate_yaml(content, file)
            validator_name = "YAML"
    elif fname == "Dockerfile" or fname.startswith("Dockerfile"):
        result = validate_dockerfile(content, file)
        validator_name = "Dockerfile"
    else:
        console.print("[yellow]Unsupported file type for validation.[/yellow]")
        sys.exit(1)

    # Display results
    status = "[bold green]✅ VALID[/bold green]" if result.is_valid else "[bold red]❌ INVALID[/bold red]"
    console.print(f"{validator_name} validation: {status}\n")

    if result.issues:
        table = Table(show_header=True)
        table.add_column("Severity", style="bold")
        table.add_column("Line")
        table.add_column("Message")

        severity_styles = {"error": "red", "warning": "yellow", "info": "blue"}

        for issue in result.issues:
            style = severity_styles.get(issue.severity, "white")
            table.add_row(
                f"[{style}]{issue.severity.upper()}[/{style}]",
                str(issue.line or "-"),
                issue.message,
            )

        console.print(table)
    else:
        console.print("[green]No issues found![/green]")

    sys.exit(0 if result.is_valid else 1)


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def inspect(path: str):
    """Show detailed project analysis as JSON."""
    import json

    try:
        result = analyze_project(path)
        console.print_json(json.dumps(result.to_dict(), indent=2))
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def _display_analysis(analysis: ProjectAnalysis):
    """Display analysis results in a rich table."""
    table = Table(title="Project Analysis", show_header=True, title_style="bold cyan")
    table.add_column("Category", style="bold")
    table.add_column("Detected")

    # Languages
    if analysis.languages:
        langs = ", ".join(
            f"{li.language.value} ({li.file_count} files){'*' if li.is_primary else ''}"
            for li in analysis.languages
        )
        table.add_row("Languages", langs)
    else:
        table.add_row("Languages", "[dim]None detected[/dim]")

    # Frameworks
    if analysis.frameworks:
        table.add_row("Frameworks", ", ".join(f.value for f in analysis.frameworks))

    # Package Managers
    if analysis.package_managers:
        table.add_row("Package Managers", ", ".join(pm.value for pm in analysis.package_managers))

    # Test Runners
    if analysis.test_runners:
        table.add_row("Test Runners", ", ".join(tr.value for tr in analysis.test_runners))

    # Linters
    if analysis.linters:
        table.add_row("Linters", ", ".join(l.value for l in analysis.linters))

    # Databases
    if analysis.databases:
        table.add_row("Databases", ", ".join(d.value for d in analysis.databases))

    # Other
    table.add_row("Docker", "✅ Found" if analysis.has_docker else "❌ Not found")
    table.add_row("Existing CI", "✅ Found" if analysis.has_ci else "❌ Not found")

    if analysis.port:
        table.add_row("Port", str(analysis.port))

    if analysis.entry_points:
        table.add_row("Entry Points", ", ".join(analysis.entry_points))

    console.print(table)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
