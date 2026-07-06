import json
from pathlib import Path

MANIFEST = (
    Path(__file__).parent.parent
    / "custom_components"
    / "transperth"
    / "manifest.json"
)


def test_manifest_required_fields() -> None:
    data = json.loads(MANIFEST.read_text())
    assert data["domain"] == "transperth"
    assert data["config_flow"] is True
    assert data["iot_class"] == "cloud_polling"
    assert data["version"]
    assert any(r.startswith("aiotransperth") for r in data["requirements"])
