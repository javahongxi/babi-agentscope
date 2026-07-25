"""Skill loader: loads Markdown-based skill definitions from directories.

Skills are loaded from three directories (higher priority overrides lower):
1. ~/.agents/skills/   — global shared skills (cross-project reuse)
2. ~/.babi/skills/     — Babi-specific skills (higher priority)
3. .qoder/skills/      — project-level skills (highest priority, relative to workspace root)

Skill file format (Markdown with YAML front-matter):
    ---
    name: code-review
    description: Perform structured code review on source files
    ---

    # Instructions
    1. Read the target file...
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Skill source directories (order = priority, later overrides earlier)
GLOBAL_DIR = Path.home() / ".agents" / "skills"
BABI_DIR = Path.home() / ".babi" / "skills"

# Project-level skills directory name (relative to workspace root)
PROJECT_SKILLS_DIR = ".qoder/skills"


@dataclass(frozen=True, slots=True)
class Skill:
    """A loaded skill definition.

    Attributes:
        name: Skill name (from front-matter or filename)
        description: Short description (from front-matter or first line)
        body: Full Markdown instructions (front-matter stripped)
        directory: Absolute path to the skill's root directory, or None for flat-file skills
    """

    name: str
    description: str
    body: str
    directory: Path | None


def load_all_skills(workspace_path: Path | None = None) -> dict[str, Skill]:
    """Load all skills from global, Babi-specific, and project-level directories.

    Project-level skills override Babi-specific skills, which override global.

    Args:
        workspace_path: Optional workspace root; if provided, loads skills
            from .qoder/skills/ within it (highest priority)

    Returns:
        Dict mapping skill name -> Skill (insertion-ordered)
    """
    skills: dict[str, Skill] = {}

    # 1. Global skills (lowest priority)
    _load_from_dir(GLOBAL_DIR, skills)

    # 2. Babi-specific skills (medium priority, overrides global)
    _load_from_dir(BABI_DIR, skills)

    # 3. Project-level skills (highest priority, relative to workspace root)
    if workspace_path is not None:
        project_skills = workspace_path / PROJECT_SKILLS_DIR
        _load_from_dir(project_skills, skills)

    logger.info("Loaded %d skill(s) from %s, %s%s", len(skills), GLOBAL_DIR, BABI_DIR,
                f", and {workspace_path / PROJECT_SKILLS_DIR}" if workspace_path else "")
    return skills


def _load_from_dir(directory: Path, target: dict[str, Skill]) -> None:
    """Scan a directory for skills. Supports two layouts:
    - Flat files: dir/my-skill.md
    - Directory format: dir/my-skill/SKILL.md
    """
    if not directory.is_dir():
        logger.debug("Skill directory does not exist, skipping: %s", directory)
        return

    try:
        entries = list(directory.iterdir())
    except OSError as e:
        logger.warning("Failed to list skill directory %s: %s", directory, e)
        return

    for entry in entries:
        if entry.is_file() and entry.suffix == ".md":
            _load_single_file(entry, target)
        elif entry.is_dir():
            # Directory-based skill: look for SKILL.md inside
            skill_md = entry / "SKILL.md"
            if skill_md.is_file():
                _load_single_file(skill_md, target)


def _load_single_file(path: Path, target: dict[str, Skill]) -> None:
    """Parse and register a single skill file."""
    try:
        skill = _parse_skill_file(path)
        if skill is not None:
            target[skill.name] = skill
            logger.debug("Loaded skill '%s' from %s", skill.name, path)
    except Exception as e:
        logger.warning("Failed to load skill from %s: %s", path, e)


def _skill_directory(skill_file: Path) -> Path | None:
    """Return the skill's root directory.

    For directory-based skills (SKILL.md inside a folder), returns that folder.
    For flat-file skills, returns None.
    """
    if skill_file.name.upper() == "SKILL.MD":
        return skill_file.parent.resolve()
    return None


def _parse_skill_file(path: Path) -> Skill | None:
    """Parse a single skill Markdown file.

    Expected format:
        ---
        name: my-skill
        description: What this skill does
        ---

        (instructions body)

    If front-matter is missing, the filename (without .md) is used as the
    name, and the first non-empty line is used as the description.
    """
    content = path.read_text(encoding="utf-8")
    file_stem = path.stem

    # For SKILL.md inside a directory, use parent dir name as fallback
    default_name = path.parent.name if file_stem.upper() == "SKILL" else file_stem

    name = default_name
    description = ""
    body = content

    # Parse YAML front-matter if present
    if content.startswith("---"):
        end_idx = content.find("---", 3)
        if end_idx > 0:
            front_matter = content[3:end_idx].strip()
            body = content[end_idx + 3:].strip()

            for line in front_matter.split("\n"):
                line = line.strip()
                if line.startswith("name:"):
                    name = line[5:].strip().strip('"').strip("'")
                elif line.startswith("description:"):
                    description = line[12:].strip().strip('"').strip("'")

    # Fallback: use first non-empty line as description
    if not description:
        for line in body.split("\n"):
            trimmed = line.strip()
            if trimmed and not trimmed.startswith("#"):
                description = trimmed[:100] + ("..." if len(trimmed) > 100 else "")
                break

    directory = _skill_directory(path)
    return Skill(name=name, description=description, body=body, directory=directory)
