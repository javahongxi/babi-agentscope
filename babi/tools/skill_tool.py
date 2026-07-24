"""Tool for discovering and activating Skills.

Skills are Markdown-based instruction sets loaded from:
- ~/.agents/skills/ — global shared skills
- ~/.babi/skills/   — Babi-specific skills (higher priority)

The agent calls list_skills to see what's available, then
use_skill to load the full instructions for a specific skill.
"""

from __future__ import annotations

from babi.skills.loader import Skill, load_all_skills
from babi.tools import text_chunk


class SkillTool:
    """Skill discovery and activation tool.

    Holds the loaded skills map and provides tool functions
    for the agent to list and use skills.
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = load_all_skills()

    @property
    def skills(self) -> dict[str, Skill]:
        """Return the loaded skills map (unmodifiable view)."""
        return dict(self._skills)

    def list_skills(self) -> "ToolChunk":
        """List all available skills. Returns skill names and descriptions.

        Call this before use_skill to discover what skills are available.
        """
        if not self._skills:
            return text_chunk(
                "No skills found. Create .md files in ~/.agents/skills/ "
                "or ~/.babi/skills/ to add skills."
            )

        lines = [f"Available skills ({len(self._skills)}):\n"]
        for skill in self._skills.values():
            lines.append(f"- **{skill.name}**: {skill.description}")
        lines.append("\nUse use_skill(skill_name) to activate a skill and get its instructions.")
        return text_chunk("\n".join(lines))

    def use_skill(self, skill_name: str) -> "ToolChunk":
        """Activate a skill by name and get its full instructions.

        The instructions will guide you through the workflow.
        Call list_skills first to see available skills.
        """
        skill = self._skills.get(skill_name)

        # Try case-insensitive match
        if skill is None:
            for key, value in self._skills.items():
                if key.lower() == skill_name.lower():
                    skill = value
                    break

        if skill is None:
            available = ", ".join(self._skills.keys())
            return text_chunk(
                f"Error: Skill '{skill_name}' not found. "
                f"Available skills: {available}. "
                "Use list_skills to see all available skills.",
                state="ERROR",
            )

        result = f"## Skill: {skill.name}\n\n{skill.body}"

        if skill.directory is not None:
            result += (
                f"\n\n**Skill directory**: `{skill.directory}`\n"
                "All relative paths in the instructions above (e.g. `scripts/...`, `references/...`) "
                "are relative to this directory. Use absolute paths when executing commands."
            )

        return text_chunk(result)
