#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pprint import pprint

from indice_pobreza_uba.config_loader import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)

    print("Config path:", cfg.config_path)
    print("Root dir:", cfg.root_dir)
    print("\nResolved paths:")
    pprint(cfg.paths)

    print("\nExample artifact path:")
    example = cfg.artifact_path(
        "stage_01_predict",
        "person_predictions",
        Q="2023Q1",
        frac=cfg.run["frac"],
        experiment_tag=cfg.run["experiment_tag"],
    )
    print(example)


if __name__ == "__main__":
    main()