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

    # Run the server
    uvicorn.run(
        "icemaker.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level.lower(),
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
