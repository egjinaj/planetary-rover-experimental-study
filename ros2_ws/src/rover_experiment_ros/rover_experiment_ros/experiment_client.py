#!/usr/bin/env python3
"""Command-line ROS 2 client for one rover experiment."""

from __future__ import annotations

import argparse
import json
import sys

import rclpy
from rclpy.node import Node

from rover_experiment_interfaces.srv import RunExperiment


def parse_arguments() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Request one rover planning experiment."
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
        "--timeout",
        type=float,
        default=60.0,
    )

    return parser.parse_known_args()


def main() -> None:
    arguments, ros_arguments = parse_arguments()

    rclpy.init(args=ros_arguments)
    node = Node("rover_experiment_client")

    client = node.create_client(
        RunExperiment,
        "run_rover_experiment",
    )

    try:
        if not client.wait_for_service(timeout_sec=10.0):
            raise RuntimeError(
                "The run_rover_experiment service is unavailable."
            )

        request = RunExperiment.Request()
        request.dataset_count = arguments.datasets
        request.memory_level = arguments.memory
        request.corruption_level = arguments.corruption
        request.seed = arguments.seed
        request.timeout_seconds = arguments.timeout

        future = client.call_async(request)

        rclpy.spin_until_future_complete(
            node,
            future,
            timeout_sec=arguments.timeout + 30.0,
        )

        if not future.done():
            raise TimeoutError(
                "The ROS service response timed out."
            )

        response = future.result()

        if response is None:
            raise RuntimeError(
                "The ROS service returned no response."
            )

        result = {
            "instance_id": response.instance_id,
            "status": response.status,
            "solved": response.solved,
            "wall_runtime_seconds": (
                response.wall_runtime_seconds
            ),
            "plan_makespan": (
                response.plan_makespan
                if response.plan_makespan >= 0
                else None
            ),
            "action_count": response.action_count,
            "move_actions": response.move_actions,
            "battery_capacity": response.battery_capacity,
            "energy_used": (
                response.energy_used
                if response.energy_used >= 0
                else None
            ),
            "battery_remaining": (
                response.battery_remaining
                if response.battery_remaining >= 0
                else None
            ),
            "battery_feasible": (
                response.battery_feasible
            ),
            "error_message": response.error_message,
        }

        print(json.dumps(result, indent=2))

    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "client_error",
                    "error_message": (
                        f"{type(error).__name__}: {error}"
                    ),
                },
                indent=2,
            )
        )
        sys.exit(1)

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
