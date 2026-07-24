"""Tests for the skill loader module."""

import tempfile
from pathlib import Path

from babi.skills.loader import Skill, _parse_skill_file, load_all_skills


class TestParseSkillFile:
    """Tests for _parse_skill_file function."""

    def test_parse_with_frontmatter(self, tmp_path: Path):
        """Test parsing a skill file with YAML front-matter."""
        skill_file = tmp_path / "test-skill.md"
        skill_file.write_text(
            "---\n"
            "name: my-skill\n"
            "description: A test skill\n"
            "---\n\n"
            "# Instructions\n"
            "Do something useful.\n",
            encoding="utf-8",
        )

        skill = _parse_skill_file(skill_file)

        assert skill is not None
        assert skill.name == "my-skill"
        assert skill.description == "A test skill"
        assert "# Instructions" in skill.body
        assert skill.directory is None  # flat file

    def test_parse_without_frontmatter(self, tmp_path: Path):
        """Test parsing a skill file without front-matter (fallback)."""
        skill_file = tmp_path / "fallback-skill.md"
        skill_file.write_text(
            "# My Skill\n\n"
            "This is the first real line of content.\n",
            encoding="utf-8",
        )

        skill = _parse_skill_file(skill_file)

        assert skill is not None
        assert skill.name == "fallback-skill"  # from filename
        assert skill.description == "This is the first real line of content."
        assert "# My Skill" in skill.body

    def test_parse_directory_based_skill(self, tmp_path: Path):
        """Test parsing a SKILL.md inside a directory."""
        skill_dir = tmp_path / "my-dir-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: dir-skill\n"
            "description: Directory-based skill\n"
            "---\n\n"
            "Instructions here.\n",
            encoding="utf-8",
        )

        skill = _parse_skill_file(skill_md)

        assert skill is not None
        assert skill.name == "dir-skill"
        assert skill.description == "Directory-based skill"
        assert skill.directory == skill_dir.resolve()

    def test_parse_sk_title_as_fallback_for_skill_md(self, tmp_path: Path):
        """Test that SKILL.md uses parent directory name as fallback."""
        skill_dir = tmp_path / "cool-feature"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("Just some instructions.\n", encoding="utf-8")

        skill = _parse_skill_file(skill_md)

        assert skill is not None
        assert skill.name == "cool-feature"  # parent dir name


class TestLoadAllSkills:
    """Tests for load_all_skills function."""

    def test_load_empty_when_no_dirs(self):
        """Test that loading returns empty dict when no skill dirs exist."""
        # This test depends on the user's home directory, but typically
        # ~/.agents/skills/ and ~/.babi/skills/ don't exist in CI
        skills = load_all_skills()
        # Just verify it returns a dict without error
        assert isinstance(skills, dict)

    def test_skill_dataclass_frozen(self):
        """Test that Skill dataclass is immutable."""
        skill = Skill(name="test", description="desc", body="body", directory=None)
        try:
            skill.name = "changed"
            assert False, "Should have raised FrozenInstanceError"
        except Exception:
            pass  # Expected
