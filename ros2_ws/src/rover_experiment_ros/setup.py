from setuptools import find_packages, setup

package_name = "rover_experiment_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        (
            "share/" + package_name,
            ["package.xml"],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Endri",
    maintainer_email="endri@example.com",
    description=(
        "ROS 2 service and client for PDDL+ rover experiments."
    ),
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            (
                "experiment_service = "
                "rover_experiment_ros.experiment_service:main"
            ),
            (
                "experiment_client = "
                "rover_experiment_ros.experiment_client:main"
            ),
        ],
    },
)
