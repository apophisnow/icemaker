"""Configuration management for icemaker control system."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class StateConfig:
    """Temperature and timeout settings for a single state."""

    target_temp: float
    timeout_seconds: int
    refill_time_seconds: int | None = None


@dataclass
class IcemakerConfig:
    """Main configuration class for icemaker control system.

    All temperature values are in Fahrenheit.
    All timeout values are in seconds.
    """

    # State configurations (from original code)
    prechill: StateConfig = field(
        default_factory=lambda: StateConfig(target_temp=32.0, timeout_seconds=120)
    )
    ice_making: StateConfig = field(
        default_factory=lambda: StateConfig(target_temp=-2.0, timeout_seconds=1500)
    )
    harvest: StateConfig = field(
        default_factory=lambda: StateConfig(target_temp=38.0, timeout_seconds=240, refill_time_seconds = 18)
    )
    rechill: StateConfig = field(
        default_factory=lambda: StateConfig(target_temp=35.0, timeout_seconds=300)
    )

    # Thresholds
    bin_full_threshold: float = 35.0

    # Hardware IDs (from original code)
    plate_sensor_id: str = "092101487373"
    bin_sensor_id: str = "3c01f0956abd"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: str = "INFO"

    # Simulation settings
    use_simulator: bool = False
    simulator_speed: float = 1.0  # Time multiplier for faster simulation

    # Polling interval for temperature readings (seconds)
    poll_interval: float = 5.0

    # Startup options
    skip_priming: bool = True  # Skip water priming on startup (default: skip)


def load_config(
    config_path: Path | None = None,
    env: str | None = None,
) -> IcemakerConfig:
    """Load configuration from YAML files and environment variables.

    Configuration is loaded with the following priority (highest to lowest):
    1. Environment variables (ICEMAKER_*)
    2. Environment-specific config (development.yaml, production.yaml)
    3. Default config (default.yaml)
    4. Hardcoded defaults

    Args:
        config_path: Path to config directory. Defaults to project config/.
        env: Environment name. Defaults to ICEMAKER_ENV or "development".

    Returns:
        Loaded IcemakerConfig instance.
    """
    config = IcemakerConfig()

    # Determine config directory
    if config_path is None:
        # Try relative to this file, then fall back to cwd
        module_dir = Path(__file__).parent
        config_path = module_dir.parent.parent / "config"
        if not config_path.exists():
            config_path = Path.cwd() / "config"

    # Load default config
    default_path = config_path / "default.yaml"
    if default_path.exists():
        config = _merge_yaml(config, default_path)
        logger.debug("Loaded default config from %s", default_path)

    # Load environment-specific config
    env = env or os.environ.get("ICEMAKER_ENV", "development")
    env_path = config_path / f"{env}.yaml"
    if env_path.exists():
        config = _merge_yaml(config, env_path)
        logger.debug("Loaded %s config from %s", env, env_path)

    # Override with environment variables
    config = _apply_env_overrides(config)

    logger.info("Configuration loaded for environment: %s", env)
    return config


def _merge_yaml(config: IcemakerConfig, path: Path) -> IcemakerConfig:
    """Merge YAML file into config."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if data is None:
        return config

    # Map YAML structure to config
    if "states" in data:
        states = data["states"]
        if "prechill" in states:
            config.prechill = StateConfig(**states["prechill"])
        if "ice_making" in states:
            config.ice_making = StateConfig(**states["ice_making"])
        if "harvest" in states:
            config.harvest = StateConfig(**states["harvest"])
        if "rechill" in states:
            config.rechill = StateConfig(**states["rechill"])

    if "thresholds" in data:
        config.bin_full_threshold = data["thresholds"].get(
            "bin_full", config.bin_full_threshold
        )

    if "hardware" in data:
        hw = data["hardware"]
        config.plate_sensor_id = hw.get("plate_sensor_id", config.plate_sensor_id)
        config.bin_sensor_id = hw.get("bin_sensor_id", config.bin_sensor_id)

    if "api" in data:
        api = data["api"]
        config.api_host = api.get("host", config.api_host)
        config.api_port = api.get("port", config.api_port)

    if "simulation" in data:
        sim = data["simulation"]
        config.use_simulator = sim.get("enabled", config.use_simulator)
        config.simulator_speed = sim.get("speed", config.simulator_speed)

    config.log_level = data.get("log_level", config.log_level)
    config.poll_interval = data.get("poll_interval", config.poll_interval)

    if "startup" in data:
        startup = data["startup"]
        config.skip_priming = startup.get("skip_priming", config.skip_priming)

    return config


def _apply_env_overrides(config: IcemakerConfig) -> IcemakerConfig:
    """Apply environment variable overrides."""
    env_map: dict[str, tuple[str, str | None, type[Any]]] = {
        "ICEMAKER_PRECHILL_TEMP": ("prechill", "target_temp", float),
        "ICEMAKER_PRECHILL_TIMEOUT": ("prechill", "timeout_seconds", int),
        "ICEMAKER_ICE_TEMP": ("ice_making", "target_temp", float),
        "ICEMAKER_ICE_TIMEOUT": ("ice_making", "timeout_seconds", int),
        "ICEMAKER_HARVEST_TEMP": ("harvest", "target_temp", float),
        "ICEMAKER_HARVEST_TIMEOUT": ("harvest", "timeout_seconds", int),
        "ICEMAKER_HARVEST_REFILL_TIME": ("harvest", "refill_time_seconds", int),
        "ICEMAKER_RECHILL_TEMP": ("rechill", "target_temp", float),
        "ICEMAKER_RECHILL_TIMEOUT": ("rechill", "timeout_seconds", int),
        "ICEMAKER_BIN_THRESHOLD": ("bin_full_threshold", None, float),
        "ICEMAKER_USE_SIMULATOR": ("use_simulator", None, _parse_bool),
        "ICEMAKER_API_HOST": ("api_host", None, str),
        "ICEMAKER_API_PORT": ("api_port", None, int),
        "ICEMAKER_LOG_LEVEL": ("log_level", None, str),
        "ICEMAKER_POLL_INTERVAL": ("poll_interval", None, float),
        "ICEMAKER_SKIP_PRIMING": ("skip_priming", None, _parse_bool),
    }

    for env_var, (attr, sub_attr, converter) in env_map.items():
        value = os.environ.get(env_var)
        if value is not None:
            try:
                converted = converter(value)
                if sub_attr:
                    setattr(getattr(config, attr), sub_attr, converted)
                else:
                    setattr(config, attr, converted)
                logger.debug("Applied env override: %s=%s", env_var, converted)
            except (ValueError, TypeError) as e:
                logger.warning("Invalid env var %s=%s: %s", env_var, value, e)

    return config


def _parse_bool(value: str) -> bool:
    """Parse boolean from string."""
    return value.lower() in ("true", "1", "yes", "on")
