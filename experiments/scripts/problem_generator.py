#!/usr/bin/env python3
"""
Generate reproducible planetary-rover PDDL+ problems.

Three models are supported:

- original: instantaneous movement
- timed: timed movement with constant edge duration
- battery: timed terrain movement with finite energy
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any


def load_config(config_path: Path) -> dict[str, Any]:
    """Load the experiment configuration."""

    if not config_path.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def format_number(value: float | int) -> str:
    """Format a number for use in PDDL."""

    numeric_value = float(value)

    if numeric_value.is_integer():
        return str(int(numeric_value))

    return f"{numeric_value:.3f}".rstrip("0").rstrip(".")


def calculate_memory_capacity(
    dataset_sizes: list[int],
    memory_ratio: float,
) -> int:
    """
    Calculate memory capacity relative to total data volume.

    Every dataset is guaranteed to fit individually.
    """

    total_size = sum(dataset_sizes)
    largest_dataset = max(dataset_sizes)

    return max(
        largest_dataset,
        math.ceil(total_size * memory_ratio),
    )


def create_map(
    site_names: list[str],
    travel_time_per_edge: float,
    timed_movement: bool,
) -> tuple[list[str], list[str]]:
    """Create the original bidirectional linear map."""

    locations = ["base", *site_names]
    connection_lines: list[str] = []
    travel_time_lines: list[str] = []

    for index in range(len(locations) - 1):
        first = locations[index]
        second = locations[index + 1]

        connection_lines.extend(
            [
                f"    (connected {first} {second})",
                f"    (connected {second} {first})",
            ]
        )

        if timed_movement:
            formatted_time = format_number(
                travel_time_per_edge
            )

            travel_time_lines.extend(
                [
                    (
                        f"    (= (travel-time {first} {second}) "
                        f"{formatted_time})"
                    ),
                    (
                        f"    (= (travel-time {second} {first}) "
                        f"{formatted_time})"
                    ),
                ]
            )

    return connection_lines, travel_time_lines


def create_battery_map(
    site_names: list[str],
    terrain_profiles: list[dict[str, Any]],
    terrain_rng: random.Random,
) -> tuple[
    list[str],
    list[str],
    list[str],
    list[dict[str, Any]],
    list[float],
]:
    """
    Create a bidirectional linear map with reproducible terrain.

    Each undirected edge receives one terrain profile. Travel time
    and energy cost are identical in both directions.
    """

    locations = ["base", *site_names]

    connection_lines: list[str] = []
    travel_time_lines: list[str] = []
    energy_cost_lines: list[str] = []
    terrain_metadata: list[dict[str, Any]] = []

    cumulative_return_times: list[float] = []
    cumulative_time = 0.0

    for index in range(len(locations) - 1):
        first = locations[index]
        second = locations[index + 1]

        profile = terrain_rng.choice(terrain_profiles)

        profile_name = str(profile["name"])
        travel_time = float(profile["travel_time"])
        energy_cost = float(profile["energy_cost"])

        if travel_time <= 0:
            raise ValueError(
                f"Terrain travel time must be positive: "
                f"{profile_name}"
            )

        if energy_cost <= 0:
            raise ValueError(
                f"Terrain energy cost must be positive: "
                f"{profile_name}"
            )

        connection_lines.extend(
            [
                f"    (connected {first} {second})",
                f"    (connected {second} {first})",
            ]
        )

        formatted_time = format_number(travel_time)
        formatted_energy = format_number(energy_cost)

        travel_time_lines.extend(
            [
                (
                    f"    (= (travel-time {first} {second}) "
                    f"{formatted_time})"
                ),
                (
                    f"    (= (travel-time {second} {first}) "
                    f"{formatted_time})"
                ),
            ]
        )

        energy_cost_lines.extend(
            [
                (
                    f"    (= (travel-energy-cost "
                    f"{first} {second}) "
                    f"{formatted_energy})"
                ),
                (
                    f"    (= (travel-energy-cost "
                    f"{second} {first}) "
                    f"{formatted_energy})"
                ),
            ]
        )

        cumulative_time += travel_time
        cumulative_return_times.append(cumulative_time)

        terrain_metadata.append(
            {
                "from": first,
                "to": second,
                "profile": profile_name,
                "travel_time": travel_time,
                "energy_cost": energy_cost,
            }
        )

    return (
        connection_lines,
        travel_time_lines,
        energy_cost_lines,
        terrain_metadata,
        cumulative_return_times,
    )


def generate_problem(
    config: dict[str, Any],
    dataset_count: int,
    memory_level: str,
    corruption_level: str,
    seed: int,
    model: str = "original",
) -> tuple[str, dict[str, Any]]:
    """Generate one reproducible PDDL+ problem."""

    if dataset_count not in config["dataset_counts"]:
        raise ValueError(
            f"Unsupported dataset count: {dataset_count}"
        )

    if memory_level not in config["memory_ratios"]:
        raise ValueError(
            f"Unsupported memory level: {memory_level}"
        )

    margin_options = config["corruption_margin_choices"]

    if corruption_level not in margin_options:
        raise ValueError(
            f"Unsupported corruption level: "
            f"{corruption_level}"
        )

    if model not in {"original", "timed", "battery"}:
        raise ValueError(
            "Model must be original, timed, or battery."
        )

    timed_movement = model in {"timed", "battery"}
    battery_model = model == "battery"

    size_min = int(config["dataset_size"]["min"])
    size_max = int(config["dataset_size"]["max"])

    encoding_min = int(config["encoding_time"]["min"])
    encoding_max = int(config["encoding_time"]["max"])

    encoding_rate = float(config["encoding_rate"])
    corruption_rate = float(config["corruption_rate"])

    # Independent random generators keep mission properties fair.
    mission_rng = random.Random(seed)
    condition_rng = random.Random(seed + 1_000_003)
    terrain_rng = random.Random(seed + 2_000_003)

    dataset_sizes = [
        mission_rng.randint(size_min, size_max)
        for _ in range(dataset_count)
    ]

    encoding_times = [
        mission_rng.randint(encoding_min, encoding_max)
        for _ in range(dataset_count)
    ]

    corruption_margin_choices = [
        float(value)
        for value in margin_options[corruption_level]
    ]

    dataset_names = [
        f"data{index}"
        for index in range(1, dataset_count + 1)
    ]

    site_names = [
        f"site{index}"
        for index in range(1, dataset_count + 1)
    ]

    memory_ratio = float(
        config["memory_ratios"][memory_level]
    )

    memory_capacity = calculate_memory_capacity(
        dataset_sizes,
        memory_ratio,
    )

    energy_cost_lines: list[str] = []
    terrain_metadata: list[dict[str, Any]] = []

    battery_capacity_multiplier: float | None = None
    optimistic_minimum_energy: float | None = None
    battery_capacity: int | None = None
    battery_headroom: float | None = None

    if battery_model:
        terrain_profiles = config["terrain_profiles"]

        (
            connection_lines,
            travel_time_lines,
            energy_cost_lines,
            terrain_metadata,
            minimum_return_times,
        ) = create_battery_map(
            site_names=site_names,
            terrain_profiles=terrain_profiles,
            terrain_rng=terrain_rng,
        )

        edge_travel_times = [
            edge["travel_time"]
            for edge in terrain_metadata
        ]

        edge_energy_costs = [
            edge["energy_cost"]
            for edge in terrain_metadata
        ]

        total_one_way_travel_time = sum(
            edge_travel_times
        )

        average_travel_time_per_edge = (
            total_one_way_travel_time
            / len(edge_travel_times)
        )

        # Minimum energy with unlimited memory:
        # travel from base to the final site and return once.
        optimistic_minimum_energy = (
            2.0 * sum(edge_energy_costs)
        )

        battery_capacity = int(
            config["battery_capacity"]
        )

        if battery_capacity <= 0:
            raise ValueError(
                "Battery capacity must be positive."
            )

        battery_capacity_multiplier = (
            battery_capacity
            / optimistic_minimum_energy
            if optimistic_minimum_energy > 0
            else None
        )

        battery_headroom = (
            battery_capacity
            - optimistic_minimum_energy
        )

        domain_name = "memory-rover-battery"

    else:
        travel_time_per_edge = float(
            config["travel_time_per_edge"]
        )

        connection_lines, travel_time_lines = create_map(
            site_names=site_names,
            travel_time_per_edge=travel_time_per_edge,
            timed_movement=timed_movement,
        )

        minimum_return_times = [
            (
                (index + 1) * travel_time_per_edge
                if timed_movement
                else 0.0
            )
            for index in range(dataset_count)
        ]

        total_one_way_travel_time = (
            dataset_count * travel_time_per_edge
            if timed_movement
            else 0.0
        )

        average_travel_time_per_edge = (
            travel_time_per_edge
            if timed_movement
            else 0.0
        )

        domain_name = (
            "memory-rover-experimental"
            if timed_movement
            else "memory-rover-plus"
        )

    problem_name = (
        f"rover-{model}"
        f"-n{dataset_count}"
        f"-mem-{memory_level}"
        f"-corr-{corruption_level}"
        f"-seed-{seed}"
    )

    data_location_lines = [
        f"    (data-at {dataset} {site})"
        for dataset, site in zip(
            dataset_names,
            site_names,
        )
    ]

    numeric_lines: list[str] = [
        "    (= (used-memory rover1) 0)",
        (
            "    (= (memory-capacity rover1) "
            f"{memory_capacity})"
        ),
    ]

    if timed_movement:
        numeric_lines.append(
            "    (= (travel-progress rover1) 0)"
        )
        numeric_lines.extend(travel_time_lines)

    if battery_model:
        numeric_lines.extend(
            [
                (
                    "    (= (battery-capacity rover1) "
                    f"{format_number(battery_capacity)})"
                ),
                (
                    "    (= (battery-level rover1) "
                    f"{format_number(battery_capacity)})"
                ),
            ]
        )
        numeric_lines.extend(energy_cost_lines)

    dataset_metadata: list[dict[str, Any]] = []

    for index, dataset_name in enumerate(dataset_names):
        dataset_size = dataset_sizes[index]
        encoding_time = encoding_times[index]

        minimum_return_time = (
            minimum_return_times[index]
        )

        earliest_direct_offload_time = max(
            float(encoding_time),
            float(minimum_return_time),
        )

        margin = condition_rng.choice(
            corruption_margin_choices
        )

        theoretically_safe = margin > 0

        loss_time = max(
            0.5,
            earliest_direct_offload_time + margin,
        )

        encoding_required = (
            encoding_time * encoding_rate
        )

        corruption_limit = (
            loss_time * corruption_rate
        )

        numeric_lines.extend(
            [
                (
                    f"    (= (data-size {dataset_name}) "
                    f"{format_number(dataset_size)})"
                ),
                f"    (= (corruption {dataset_name}) 0)",
                (
                    f"    (= (corruption-limit "
                    f"{dataset_name}) "
                    f"{format_number(corruption_limit)})"
                ),
                (
                    f"    (= (corruption-rate "
                    f"{dataset_name}) "
                    f"{format_number(corruption_rate)})"
                ),
                (
                    f"    (= (encoding-progress "
                    f"{dataset_name}) 0)"
                ),
                (
                    f"    (= (encoding-required "
                    f"{dataset_name}) "
                    f"{format_number(encoding_required)})"
                ),
                (
                    f"    (= (encoding-rate "
                    f"{dataset_name}) "
                    f"{format_number(encoding_rate)})"
                ),
            ]
        )

        dataset_metadata.append(
            {
                "dataset": dataset_name,
                "site": site_names[index],
                "size": dataset_size,
                "encoding_time": encoding_time,
                "minimum_return_time": (
                    minimum_return_time
                ),
                "earliest_direct_offload_time": (
                    earliest_direct_offload_time
                ),
                "corruption_margin": margin,
                "loss_time": loss_time,
                "theoretically_safe": (
                    theoretically_safe
                ),
            }
        )

    goal_lines: list[str] = []

    for dataset_name in dataset_names:
        goal_lines.extend(
            [
                f"      (offloaded {dataset_name})",
                f"      (not (lost {dataset_name}))",
            ]
        )

    problem_text = "\n".join(
        [
            f"(define (problem {problem_name})",
            f"  (:domain {domain_name})",
            "",
            "  (:objects",
            "    rover1 - rover",
            (
                f"    base {' '.join(site_names)} "
                "- location"
            ),
            f"    {' '.join(dataset_names)} - data",
            "  )",
            "",
            "  (:init",
            "    (at rover1 base)",
            "    (base base)",
            *connection_lines,
            *data_location_lines,
            *numeric_lines,
            "  )",
            "",
            "  (:goal",
            "    (and",
            *goal_lines,
            "    )",
            "  )",
            "",
            "  (:metric minimize (total-time))",
            ")",
            "",
        ]
    )

    safe_dataset_count = sum(
        dataset["theoretically_safe"]
        for dataset in dataset_metadata
    )

    metadata = {
        "instance_id": problem_name,
        "model": model,
        "seed": seed,
        "dataset_count": dataset_count,
        "memory_level": memory_level,
        "memory_ratio": memory_ratio,
        "memory_capacity": memory_capacity,
        "total_dataset_size": sum(dataset_sizes),
        "corruption_level": corruption_level,
        "average_travel_time_per_edge": (
            average_travel_time_per_edge
        ),
        "total_one_way_travel_time": (
            total_one_way_travel_time
        ),
        "battery_capacity_multiplier": (
            battery_capacity_multiplier
        ),
        "optimistic_minimum_energy": (
            optimistic_minimum_energy
        ),
        "battery_capacity": battery_capacity,
        "battery_headroom": battery_headroom,
        "terrain_edges": terrain_metadata,
        "safe_dataset_count": safe_dataset_count,
        "unsafe_dataset_count": (
            dataset_count - safe_dataset_count
        ),
        "datasets": dataset_metadata,
    }

    return problem_text, metadata

def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Generate one rover PDDL+ problem."
    )

    parser.add_argument(
        "--datasets",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--memory",
        choices=["low", "medium", "high"],
        required=True,
    )

    parser.add_argument(
        "--corruption",
        choices=["low", "medium", "high"],
        required=True,
    )

    parser.add_argument(
        "--seed",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--model",
        choices=["original", "timed", "battery"],
        default="original",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "experiments/config/experiment_config.json"
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "experiments/generated_problems"
        ),
    )

    return parser.parse_args()


def main() -> int:
    """Generate and save one problem."""

    arguments = parse_arguments()

    try:
        config = load_config(arguments.config)

        problem_text, metadata = generate_problem(
            config=config,
            dataset_count=arguments.datasets,
            memory_level=arguments.memory,
            corruption_level=arguments.corruption,
            seed=arguments.seed,
            model=arguments.model,
        )

        arguments.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        instance_id = metadata["instance_id"]

        problem_path = (
            arguments.output_dir
            / f"{instance_id}.pddl"
        )

        metadata_path = (
            arguments.output_dir
            / f"{instance_id}.json"
        )

        problem_path.write_text(
            problem_text,
            encoding="utf-8",
        )

        metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

        print(
            json.dumps(
                {
                    "status": "generated",
                    "problem_file": str(problem_path),
                    "metadata_file": str(metadata_path),
                    **metadata,
                },
                indent=2,
            )
        )

        return 0

    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "generation_error",
                    "error": (
                        f"{type(error).__name__}: {error}"
                    ),
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
