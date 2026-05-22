"""Pytest wrapper for the cross-file data integrity checker."""
import sys
from pathlib import Path

# Ensure the extension root is on sys.path so we can import scripts.*
_EXTENSION_ROOT = Path(__file__).resolve().parent.parent
if str(_EXTENSION_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXTENSION_ROOT))

from scripts.check_data_integrity import check_all  # noqa: E402


def test_data_integrity_no_errors() -> None:
    """All data files must pass the integrity checker with zero errors."""
    issues = check_all()
    errors = [i for i in issues if i.severity == "error"]
    assert not errors, (
        f"data integrity errors found ({len(errors)}):\n"
        + "\n".join(f"  {i.file}: {i.message}" for i in errors)
    )
