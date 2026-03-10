#!/usr/bin/env python3
from __future__ import annotations

import argparse

from indice_pobreza_uba.config_loader import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)

    smoke_cfg = cfg.execution["smoke"]
    if not smoke_cfg["enabled"]:
        raise SystemExit("Smoke mode is disabled in config.")

    print("Smoke run")
    print("Years:", smoke_cfg["years"])
    print("Quarters:", smoke_cfg["quarters"])
    print("Max rows:", smoke_cfg["max_rows"])
    print("Stages:", smoke_cfg["stages"])

    # Placeholder only.
    # Later:
    # 1. validate input existence
    # 2. run stage_01_predict subset
    # 3. run stage_02_poverty subset
    # 4. write run manifest
    print("Smoke runner placeholder completed.")


if __name__ == "__main__":
    main()