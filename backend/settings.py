"""Settings persistence for Google Sheets connection config."""
import json
import logging
import os

logger = logging.getLogger(__name__)


class SettingsManager:
    """Save/load Google Sheets connection settings to a JSON file."""

    DEFAULTS = {
        "spreadsheet_id": "",
        "service_account_file": "",
    }

    def __init__(self, settings_path: str):
        self._path = settings_path

    def load(self) -> dict:
        """Load settings from disk, merging with defaults."""
        defaults = dict(self.DEFAULTS)
        if os.path.exists(self._path):
            with open(self._path, 'r') as f:
                content = f.read().strip()
            if content:
                try:
                    data = json.loads(content)
                    defaults.update(data)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Corrupted settings file %s; falling back to defaults. Error: %s",
                        self._path, exc,
                    )
        return defaults

    def save(self, config: dict) -> None:
        """Save settings to disk, merging with existing values."""
        existing = self.load()
        existing.update(config)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'w') as f:
            json.dump(existing, f, indent=2)
