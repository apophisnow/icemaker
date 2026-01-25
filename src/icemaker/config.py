"""Configuration management for icemaker control system."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def _is_raspberry_pi() -> bool:
    """Detect if running on a Raspberry Pi."""
    try:
        with open("/proc/cpuinfo") as f:
            cpuinfo = f.read()
            return "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
    except (FileNotFoundError, PermissionError):
        return False


def _load_dotenv(env_path: Path) -> None:
    """Load environment variables from .env file."""
    if not env_path.exists():
        return

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value


@dataclass
class StateConfig:
    """Temperature and timeout settings for a single state."""

    target_temp: float
    timeout_seconds: int


@dataclass
class PrimingConfig:
    """Configuration for the water priming sequence.

    The priming sequence runs in 3 phases:
    1. Water valve open (flush/rinse lines)
    2. Recirculating pump on (prime pump)
    3. Water valve open (fill reservoir)
    """

    flush_time_seconds: int = 60  # Phase 1: Flush/rinse water lines
    pump_time_seconds: int = 15   # Phase 2: Prime the pump
    fill_time_seconds: int = 15   # Phase 3: Fill reservoir (also used during harvest)


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
        default_factory=lambda: StateConfig(target_temp=38.0, timeout_seconds=240)
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

    # Standby timeout - auto-transition to OFF after this many seconds in STANDBY
    # Ice cutter stays on during this period to ensure all ice is cut
    standby_timeout: float = 1200.0  # 20 minutes

    # Startup options
    priming_enabled: bool = False  # Run water priming on power on (default: disabled)
    priming: PrimingConfig = field(default_factory=PrimingConfig)

    # Data directory for persistent storage (cycle count, etc.)
    data_dir: str = "data"


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
            On Raspberry Pi, defaults to "production".

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

    # Load .env file from project root (config_path/../.env)
    project_root = config_path.parent
    _load_dotenv(project_root / ".env")

    # Load default config
    default_path = config_path / "default.yaml"
    if default_path.exists():
        config = _merge_yaml(config, default_path)
        logger.debug("Loaded default config from %s", default_path)

    # Determine environment: explicit > env var > auto-detect Pi > development
    if env is None:
        env = os.environ.get("ICEMAKER_ENV")
    if env is None:
        if _is_raspberry_pi():
            env = "production"
            logger.info("Raspberry Pi detected, using production environment")
        else:
            env = "development"

    env_config_path = config_path / f"{env}.yaml"
    if env_config_path.exists():
        config = _merge_yaml(config, env_config_path)
        logger.debug("Loaded %s config from %s", env, env_config_path)

    # Load runtime config (user-modified settings) if it exists
    config = load_runtime_config(config)

    # Override with environment variables (highest priority)
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
        config.priming_enabled = startup.get("priming_enabled", config.priming_enabled)
        if "priming" in startup:
            priming = startup["priming"]
            config.priming.flush_time_seconds = priming.get("flush_time_seconds", config.priming.flush_time_seconds)
            config.priming.pump_time_seconds = priming.get("pump_time_seconds", config.priming.pump_time_seconds)
            config.priming.fill_time_seconds = priming.get("fill_time_seconds", config.priming.fill_time_seconds)

    config.standby_timeout = data.get("standby_timeout", config.standby_timeout)

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
        "ICEMAKER_RECHILL_TEMP": ("rechill", "target_temp", float),
        "ICEMAKER_RECHILL_TIMEOUT": ("rechill", "timeout_seconds", int),
        "ICEMAKER_BIN_THRESHOLD": ("bin_full_threshold", None, float),
        "ICEMAKER_USE_SIMULATOR": ("use_simulator", None, _parse_bool),
        "ICEMAKER_API_HOST": ("api_host", None, str),
        "ICEMAKER_API_PORT": ("api_port", None, int),
        "ICEMAKER_LOG_LEVEL": ("log_level", None, str),
        "ICEMAKER_POLL_INTERVAL": ("poll_interval", None, float),
        "ICEMAKER_STANDBY_TIMEOUT": ("standby_timeout", None, float),
        "ICEMAKER_PRIMING_ENABLED": ("priming_enabled", None, _parse_bool),
        "ICEMAKER_PRIMING_FLUSH_TIME": ("priming", "flush_time_seconds", int),
        "ICEMAKER_PRIMING_PUMP_TIME": ("priming", "pump_time_seconds", int),
        "ICEMAKER_PRIMING_FILL_TIME": ("priming", "fill_time_seconds", int),
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


def get_runtime_config_path(data_dir: str = "data") -> Path:
    """Get path to the runtime configuration file.

    Args:
        data_dir: Data directory path.

    Returns:
        Path to runtime_config.yaml
    """
    path = Path(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path / "runtime_config.yaml"


def save_runtime_config(config: IcemakerConfig, data_dir: str | None = None) -> None:
    """Save user-modifiable configuration to runtime config file.

    Only saves settings that users can modify via the API, not hardware
    IDs, API settings, or simulation settings.

    Args:
        config: Current configuration to save.
        data_dir: Data directory path. Uses config.data_dir if None.
    """
    if data_dir is None:
        data_dir = config.data_dir

    runtime_data = {
        "states": {
            "prechill": {
                "target_temp": config.prechill.target_temp,
                "timeout_seconds": config.prechill.timeout_seconds,
            },
            "ice_making": {
                "target_temp": config.ice_making.target_temp,
                "timeout_seconds": config.ice_making.timeout_seconds,
            },
            "harvest": {
                "target_temp": config.harvest.target_temp,
                "timeout_seconds": config.harvest.timeout_seconds,
            },
            "rechill": {
                "target_temp": config.rechill.target_temp,
                "timeout_seconds": config.rechill.timeout_seconds,
            },
        },
        "thresholds": {
            "bin_full": config.bin_full_threshold,
        },
        "startup": {
            "priming_enabled": config.priming_enabled,
            "priming": {
                "flush_time_seconds": config.priming.flush_time_seconds,
                "pump_time_seconds": config.priming.pump_time_seconds,
                "fill_time_seconds": config.priming.fill_time_seconds,
            },
        },
        "standby_timeout": config.standby_timeout,
    }

    path = get_runtime_config_path(data_dir)
    try:
        with open(path, "w") as f:
            yaml.safe_dump(runtime_data, f, default_flow_style=False)
        logger.info("Saved runtime config to %s", path)
    except OSError as e:
        logger.error("Failed to save runtime config: %s", e)


def load_runtime_config(config: IcemakerConfig) -> IcemakerConfig:
    """Load and apply runtime configuration if it exists.

    Args:
        config: Base configuration to apply runtime settings to.

    Returns:
        Configuration with runtime settings applied.
    """
    path = get_runtime_config_path(config.data_dir)
    if not path.exists():
        logger.debug("No runtime config found at %s", path)
        return config

    try:
        config = _merge_yaml(config, path)
        logger.info("Loaded runtime config from %s", path)
    except (OSError, yaml.YAMLError) as e:
        logger.warning("Failed to load runtime config: %s", e)

    return config


def reset_to_factory_defaults(data_dir: str = "data") -> bool:
    """Reset configuration to factory defaults by removing runtime config.

    Args:
        data_dir: Data directory path.

    Returns:
        True if reset successful, False if no runtime config existed.
    """
    path = get_runtime_config_path(data_dir)
    if path.exists():
        try:
            path.unlink()
            logger.info("Reset to factory defaults - removed %s", path)
            return True
        except OSError as e:
            logger.error("Failed to remove runtime config: %s", e)
            return False
    return False
