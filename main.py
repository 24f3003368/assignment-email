
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

# Allow browser-based graders to call this API from another origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# Configuration keys that should become integers.
INTEGER_KEYS = {"port", "workers"}

# All values in this set use boolean conversion.
BOOLEAN_KEYS = {"debug"}


def coerce_value(key: str, value):
    """Convert a configuration value to the required type."""
    if key in INTEGER_KEYS:
        return int(value)

    if key in BOOLEAN_KEYS:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {
            "true", "1", "yes", "on"
        }

    # All other keys are strings.
    return str(value)


def normalize_layer(layer: dict) -> dict:
    """Normalize key names and apply the workers alias."""
    normalized = {}

    for key, value in layer.items():
        if value is None:
            continue

        key = str(key).strip().lower()

        if key.startswith("app_"):
            key = key[4:]

        if key == "num_workers":
            key = "workers"

        normalized[key] = value

    return normalized


def load_effective_config(overrides: list[str]) -> dict:
    # Layer 1: hardcoded defaults.
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML.
    environment = os.environ.get("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"

    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}

        config.update(normalize_layer(yaml_config))

    # Layer 3: .env file.
    # dotenv_values reads the file without replacing os.environ.
    env_file = dotenv_values(BASE_DIR / ".env")
    config.update(normalize_layer(env_file))

    # Layer 4: real OS environment variables.
    os_config = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_")
    }
    config.update(normalize_layer(os_config))

    # Layer 5: request-supplied overrides.
    for item in overrides:
        key, separator, value = item.partition("=")

        if not separator or not key.strip():
            continue

        key = key.strip().lower()

        if key == "num_workers":
            key = "workers"

        config[key] = value

    # Convert final values only after all layers have been merged.
    config = {
        key: coerce_value(key, value)
        for key, value in config.items()
    }

    # Never expose the real API key in the response.
    config["api_key"] = "****"

    return config


@app.get("/effective-config")
def effective_config(
    set: list[str] = Query(default=[]),
):
    return load_effective_config(set)

