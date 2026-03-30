import os, sys, logging
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    shopify_access_token: str
    shopify_store: str
    shopify_api_version: str
    font_path: str
    output_dir: str

def load_config() -> Config:
    required = {
        "SHOPIFY_ACCESS_TOKEN": os.getenv("SHOPIFY_ACCESS_TOKEN"),
        "SHOPIFY_STORE": os.getenv("SHOPIFY_STORE"),
        "FONT_PATH": os.getenv("FONT_PATH"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Copy .env.example to .env and fill in the values.", file=sys.stderr)
        sys.exit(1)

    output_dir = os.getenv("OUTPUT_DIR", "output")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    _configure_logging(output_dir)

    return Config(
        shopify_access_token=required["SHOPIFY_ACCESS_TOKEN"],
        shopify_store=required["SHOPIFY_STORE"],
        shopify_api_version=os.getenv("SHOPIFY_API_VERSION", "2024-04"),
        font_path=required["FONT_PATH"],
        output_dir=output_dir,
    )

def _configure_logging(output_dir: str):
    log_path = Path(output_dir) / "run.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),   # WARNING+ to stderr via root logger level below
        ],
    )
    # Silence DEBUG/INFO on stderr — only WARNING+ to console
    logging.getLogger().handlers[1].setLevel(logging.WARNING)
