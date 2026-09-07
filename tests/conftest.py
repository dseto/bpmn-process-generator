from pathlib import Path
import pytest

@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent

@pytest.fixture(scope="session")
def tests_dir(project_root: Path) -> Path:
    return project_root / "tests"

@pytest.fixture(scope="session")
def scripts_dir(project_root: Path) -> Path:
    return project_root / "scripts"

@pytest.fixture(scope="session")
def references_dir(project_root: Path) -> Path:
    return project_root / "references"

@pytest.fixture(scope="session")
def template_path(project_root: Path) -> Path:
    return project_root / "assets" / "bpmn-editor-template.html"

@pytest.fixture(scope="session")
def existing_bpmn_files(tests_dir: Path):
    """Returns all .bpmn test files found in the tests directory."""
    files = sorted(tests_dir.glob("*.bpmn"))
    assert len(files) >= 6, f"Expected at least 6 BPMN test files in {tests_dir}, found {len(files)}"
    return files
