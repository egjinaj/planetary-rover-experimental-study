#!/usr/bin/env python3
"""ROS 2 service for running one timed-rover planning experiment."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

import rclpy
from rclpy.node import Node

from rover_experiment_interfaces.srv import RunExperiment


def find_project_root() -> Path:
    """Locate the planetary-rover repository."""

    starting_points: list[Path] = []

    environment_root = os.environ.get("ROVER_PROJECT_ROOT")

    if environment_root:
        starting_points.append(
            Path(environment_root).expanduser()
        )

    starting_points.append(Path.cwd())

    for starting_point in starting_points:
        resolved = starting_point.resolve()

        for candidate in [resolved, *resolved.parents]:
            generator = (
                candidate
                / "experiments/scripts/problem_generator.py"
            )
            runner = (
                candidate
                / "experiments/scripts/planner_runner.py"
            )

            if generator.is_file() and runner.is_file():
                return candidate

    raise FileNotFoundError(
        "Could not locate the rover project root. "
        "Set the ROVER_PROJECT_ROOT environment variable."
    )


def parse_json_output(
    process: subprocess.CompletedProcess[str],
    command_name: str,
) -> dict[str, Any]:
    """Parse a JSON response produced by an experiment script."""

    output = process.stdout.strip()

    if not output:
        raise RuntimeError(
            f"{command_name} produced no JSON output.\n"
            f"stderr: {process.stderr.strip()}"
        )

    try:
        result = json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"{command_name} returned invalid JSON.\n"
            f"stdout: {output}\n"
            f"stderr: {process.stderr.strip()}"
        ) from error

    return result


class RoverExperimentService(Node):
    """Expose the PDDL+ experiment runner as a ROS 2 service."""

    def __init__(self) -> None:
        super().__init__("rover_experiment_service")

        self.project_root = find_project_root()

        self.generator_script = (
            self.project_root
            / "experiments/scripts/problem_generator.py"
        )

        self.runner_script = (
            self.project_root
            / "experiments/scripts/planner_runner.py"
        )

        self.config_path = (
            self.project_root
            / "experiments/config/experiment_config.json"
        )

        self.domain_path = (
            self.project_root
            / "planning_models/pddl_plus/"
            "domain-memory-rover-experimental.pddl"
        )

        self.generated_directory = (
            self.project_root
            / "experiments/generated_problems/ros_runs"
        )

        self.raw_output_directory = (
            self.project_root
            / "experiments/raw_outputs/ros_runs"
        )

        self.result_directory = (
            self.project_root
            / "experiments/results/ros_runs"
        )

        self.generated_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.raw_output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.result_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.service = self.create_service(
            RunExperiment,
            "run_rover_experiment",
            self.run_experiment_callback,
        )

        self.get_logger().info(
            "Rover experiment service is ready."
        )
        self.get_logger().info(
            f"Project root: {self.project_root}"
        )

    def validate_request(
        self,
        request: RunExperiment.Request,
    ) -> None:
        """Validate experiment parameters before running ENHSP."""

        config = json.loads(
            self.config_path.read_text(encoding="utf-8")
        )

        if request.dataset_count not in config["dataset_counts"]:
            raise ValueError(
                "dataset_count must be one of "
                f"{config['dataset_counts']}."
            )

        if request.memory_level not in config["memory_ratios"]:
            raise ValueError(
                "memory_level must be low, medium, or high."
            )

        if (
            request.corruption_level
            not in config["corruption_margin_choices"]
        ):
            raise ValueError(
                "corruption_level must be low, medium, or high."
            )

        if request.seed < 0:
            raise ValueError("seed must be non-negative.")

        if request.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

    def run_generator(
        self,
        request: RunExperiment.Request,
    ) -> dict[str, Any]:
        """Generate one timed PDDL+ problem."""

        command = [
            sys.executable,
            str(self.generator_script),
            "--model",
            "timed",
            "--datasets",
            str(request.dataset_count),
            "--memory",
            request.memory_level,
            "--corruption",
            request.corruption_level,
            "--seed",
            str(request.seed),
            "--config",
            str(self.config_path),
            "--output-dir",
            str(self.generated_directory),
        ]

        process = subprocess.run(
            command,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        generation_result = parse_json_output(
            process,
            "problem_generator.py",
        )

        if process.returncode != 0:
            raise RuntimeError(
                generation_result.get(
                    "error",
                    "Problem generation failed.",
                )
            )

        return generation_result

    def run_planner(
        self,
        problem_path: Path,
        raw_output_path: Path,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """Run ENHSP through the existing planner runner."""

        command = [
            sys.executable,
            str(self.runner_script),
            "--domain",
            str(self.domain_path),
            "--problem",
            str(problem_path),
            "--output",
            str(raw_output_path),
            "--timeout",
            str(timeout_seconds),
        ]

        process = subprocess.run(
            command,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 30,
            check=False,
        )

        return parse_json_output(
            process,
            "planner_runner.py",
        )

    def run_experiment_callback(
        self,
        request: RunExperiment.Request,
        response: RunExperiment.Response,
    ) -> RunExperiment.Response:
        """Generate, run, save, and return one experiment."""

        try:
            self.validate_request(request)

            self.get_logger().info(
                "Received experiment request: "
                f"datasets={request.dataset_count}, "
                f"memory={request.memory_level}, "
                f"corruption={request.corruption_level}, "
                f"seed={request.seed}, "
                f"timeout={request.timeout_seconds}"
            )

            generation = self.run_generator(request)

            instance_id = generation["instance_id"]
            problem_path = Path(generation["problem_file"])

            if not problem_path.is_absolute():
                problem_path = (
                    self.project_root / problem_path
                ).resolve()

            raw_output_path = (
                self.raw_output_directory
                / f"{instance_id}.txt"
            )

            planner_result = self.run_planner(
                problem_path=problem_path,
                raw_output_path=raw_output_path,
                timeout_seconds=request.timeout_seconds,
            )

            result_path = (
                self.result_directory
                / f"{instance_id}.json"
            )

            result_path.write_text(
                json.dumps(planner_result, indent=2),
                encoding="utf-8",
            )

            response.instance_id = instance_id
            response.status = str(
                planner_result.get("status", "unknown")
            )
            response.solved = bool(
                planner_result.get("solved", False)
            )
            response.wall_runtime_seconds = float(
                planner_result.get(
                    "wall_runtime_seconds",
                    0.0,
                )
                or 0.0
            )

            plan_makespan = planner_result.get(
                "plan_makespan"
            )

            response.plan_makespan = (
                float(plan_makespan)
                if plan_makespan is not None
                else -1.0
            )

            response.action_count = int(
                planner_result.get("action_count", 0)
                or 0
            )

            response.move_actions = int(
                planner_result.get("move_actions", 0)
                or 0
            )

            response.error_message = str(
                planner_result.get("error_message", "")
                or ""
            )

            self.get_logger().info(
                f"{instance_id}: {response.status}, "
                f"runtime={response.wall_runtime_seconds:.3f}s"
            )

        except Exception as error:
            self.get_logger().error(
                f"Experiment failed: {error}"
            )

            self.get_logger().debug(
                traceback.format_exc()
            )

            response.instance_id = ""
            response.status = "error"
            response.solved = False
            response.wall_runtime_seconds = 0.0
            response.plan_makespan = -1.0
            response.action_count = 0
            response.move_actions = 0
            response.error_message = (
                f"{type(error).__name__}: {error}"
            )

        return response


def main(args: list[str] | None = None) -> None:
    """Start the ROS 2 experiment service."""

    rclpy.init(args=args)

    node = RoverExperimentService()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
