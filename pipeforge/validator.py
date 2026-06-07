"""Validate generated CI/CD configuration files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml


@dataclass
class ValidationIssue:
    """A single validation issue found in a config file."""
    severity: str  # "error", "warning", "info"
    message: str
    line: int | None = None
    file_path: str = ""


@dataclass
class ValidationResult:
    """Result of validating a configuration file."""
    file_path: str
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


def validate_yaml(content: str, file_path: str = "") -> ValidationResult:
    """Validate that content is valid YAML."""
    issues = []
    try:
        parsed = yaml.safe_load(content)
        if parsed is None:
            issues.append(ValidationIssue("warning", "YAML file is empty", file_path=file_path))
        elif not isinstance(parsed, dict):
            issues.append(ValidationIssue("error", "YAML root must be a mapping", file_path=file_path))
    except yaml.YAMLError as e:
        line = getattr(e, "problem_mark", None)
        line_num = line.line + 1 if line else None
        issues.append(ValidationIssue("error", f"Invalid YAML: {e}", line=line_num, file_path=file_path))

    return ValidationResult(
        file_path=file_path,
        is_valid=not any(i.severity == "error" for i in issues),
        issues=issues,
    )


def validate_github_actions(content: str, file_path: str = "") -> ValidationResult:
    """Validate a GitHub Actions workflow file."""
    result = validate_yaml(content, file_path)
    if not result.is_valid:
        return result

    try:
        workflow = yaml.safe_load(content)
    except yaml.YAMLError:
        return result

    issues = list(result.issues)

    # Check required top-level keys
    if "name" not in workflow:
        issues.append(ValidationIssue("warning", "Missing 'name' field", file_path=file_path))

    # PyYAML parses bare `on:` as boolean True key
    has_on = "on" in workflow or True in workflow
    if not has_on:
        issues.append(ValidationIssue("error", "Missing 'on' trigger definition", file_path=file_path))

    if "jobs" not in workflow:
        issues.append(ValidationIssue("error", "Missing 'jobs' section", file_path=file_path))
    elif isinstance(workflow["jobs"], dict):
        for job_name, job_config in workflow["jobs"].items():
            if not isinstance(job_config, dict):
                issues.append(ValidationIssue("error", f"Job '{job_name}' must be a mapping", file_path=file_path))
                continue

            if "runs-on" not in job_config:
                issues.append(ValidationIssue("error", f"Job '{job_name}' missing 'runs-on'", file_path=file_path))

            if "steps" not in job_config:
                issues.append(ValidationIssue("error", f"Job '{job_name}' missing 'steps'", file_path=file_path))
            elif isinstance(job_config["steps"], list):
                for i, step in enumerate(job_config["steps"]):
                    if not isinstance(step, dict):
                        continue
                    if "uses" not in step and "run" not in step:
                        issues.append(ValidationIssue(
                            "warning",
                            f"Job '{job_name}' step {i+1} has neither 'uses' nor 'run'",
                            file_path=file_path,
                        ))

    # Check for pinned action versions
    action_pattern = re.compile(r"uses:\s+([^@\s]+)@([\w.]+)")
    for match in action_pattern.finditer(content):
        action, version = match.groups()
        if version in ("master", "main"):
            issues.append(ValidationIssue(
                "warning",
                f"Action '{action}' uses branch '{version}' — pin to a specific version for reproducibility",
                file_path=file_path,
            ))

    return ValidationResult(
        file_path=file_path,
        is_valid=not any(i.severity == "error" for i in issues),
        issues=issues,
    )


def validate_gitlab_ci(content: str, file_path: str = "") -> ValidationResult:
    """Validate a GitLab CI configuration file."""
    result = validate_yaml(content, file_path)
    if not result.is_valid:
        return result

    try:
        config = yaml.safe_load(content)
    except yaml.YAMLError:
        return result

    issues = list(result.issues)

    # Check for stages
    if "stages" not in config:
        issues.append(ValidationIssue("warning", "No 'stages' defined — GitLab uses default stages", file_path=file_path))

    # Check jobs have valid stages
    stages = config.get("stages", [])
    reserved_keys = {"stages", "variables", "cache", "default", "include", "workflow", "image", "services", "before_script", "after_script"}

    for key, value in config.items():
        if key in reserved_keys or not isinstance(value, dict):
            continue
        job_stage = value.get("stage")
        if job_stage and stages and job_stage not in stages:
            issues.append(ValidationIssue(
                "error",
                f"Job '{key}' uses stage '{job_stage}' which is not in stages list",
                file_path=file_path,
            ))
        if "script" not in value and "trigger" not in value:
            issues.append(ValidationIssue(
                "error",
                f"Job '{key}' is missing 'script' or 'trigger'",
                file_path=file_path,
            ))

    return ValidationResult(
        file_path=file_path,
        is_valid=not any(i.severity == "error" for i in issues),
        issues=issues,
    )


def validate_dockerfile(content: str, file_path: str = "") -> ValidationResult:
    """Validate a Dockerfile for common issues."""
    issues = []
    lines = content.strip().split("\n")

    has_from = False
    has_user = False
    has_healthcheck = False
    uses_latest = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("FROM"):
            has_from = True
            if ":latest" in stripped or ("::" not in stripped and "@" not in stripped and ":" not in stripped.split()[-1] and "AS" not in stripped.upper()):
                # Check if the image tag is 'latest' or missing
                parts = stripped.split()
                if len(parts) >= 2:
                    image = parts[1]
                    if ":latest" in image:
                        uses_latest = True
                        issues.append(ValidationIssue(
                            "warning",
                            f"Using ':latest' tag — pin to a specific version for reproducibility",
                            line=i,
                            file_path=file_path,
                        ))
                    elif ":" not in image and "@" not in image:
                        issues.append(ValidationIssue(
                            "warning",
                            f"No tag specified for image '{image}' — pin to a specific version",
                            line=i,
                            file_path=file_path,
                        ))

        if stripped.startswith("USER") and not stripped.startswith("USER root"):
            has_user = True

        if stripped.startswith("HEALTHCHECK"):
            has_healthcheck = True

        # Check for common anti-patterns
        if stripped.startswith("RUN") and "apt-get install" in stripped and "rm -rf /var/lib/apt/lists" not in stripped:
            # Check if multi-line continuation covers cleanup
            full_cmd = stripped
            j = i
            while full_cmd.endswith("\\") and j < len(lines):
                full_cmd += lines[j]
                j += 1
            if "rm -rf /var/lib/apt/lists" not in full_cmd:
                issues.append(ValidationIssue(
                    "info",
                    "apt-get install without cleanup — add 'rm -rf /var/lib/apt/lists/*' to reduce image size",
                    line=i,
                    file_path=file_path,
                ))

    if not has_from:
        issues.append(ValidationIssue("error", "Dockerfile has no FROM instruction", file_path=file_path))
    if not has_user:
        issues.append(ValidationIssue("info", "No USER instruction — container runs as root by default", file_path=file_path))
    if not has_healthcheck:
        issues.append(ValidationIssue("info", "No HEALTHCHECK — consider adding one for production", file_path=file_path))

    return ValidationResult(
        file_path=file_path,
        is_valid=not any(i.severity == "error" for i in issues),
        issues=issues,
    )
