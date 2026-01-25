"""Entry point for icemaker control system."""

import argparse
import logging
import sys


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Icemaker Control System",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind API server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind API server to (default: 8000)",
    )
    parser.add_argument(
        "--simulator",
        action="store_true",
        help="Use physics-based simulator instead of real hardware",
    )
    parser.add_argument(
        "--env",
        default=None,
        help="Configuration environment (default: ICEMAKER_ENV or 'development')",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--no-access-log",
        action="store_true",
        help="Disable access logging (reduces I/O on Pi)",
    )
    parser.add_argument(
        "--limit-concurrency",
        type=int,
        default=None,
        help="Limit concurrent connections (helps on memory-constrained devices)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set environment variables for configuration
    import os
    if args.simulator:
        os.environ["ICEMAKER_USE_SIMULATOR"] = "true"
    if args.env:
        os.environ["ICEMAKER_ENV"] = args.env

    # Import uvicorn here to avoid import errors if not installed
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required. Install with: pip install uvicorn[standard]")
        return 1

    # Build uvicorn config
    uvicorn_kwargs = {
        "host": args.host,
        "port": args.port,
        "reload": args.reload,
        "log_level": args.log_level.lower(),
        "access_log": not args.no_access_log,
    }

    # Add concurrency limit if specified (helps on Pi)
    if args.limit_concurrency:
        uvicorn_kwargs["limit_concurrency"] = args.limit_concurrency

    # Run the server
    uvicorn.run("icemaker.api.app:app", **uvicorn_kwargs)

    return 0


if __name__ == "__main__":
    sys.exit(main())
