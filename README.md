# Battery-Constrained Planetary Rover Planning

This repository contains a reproducible PDDL+ study of a planetary rover operating with limited onboard memory, a fixed battery budget, terrain-dependent travel costs, and scientific data that degrades over time.

The project combines:

- a PDDL+ rover domain;
- deterministic mission generation;
- automated ENHSP execution and output parsing;
- a 135-instance final experiment;
- an executed Jupyter notebook with statistical analysis;
- a ROS 2 service and client;
- an IEEE-style research paper.

## Research question

**How do onboard memory, mission size, and time-dependent data degradation affect the feasibility, efficiency, and planning difficulty of a battery-constrained rover mission?**

## Mission model

The rover travels from a base station to a sequence of science sites. At each site, it may collect and encode a dataset. Collected data occupies onboard memory and must be returned to base before corruption reaches its loss threshold.

The final model includes:

- timed bidirectional movement;
- four terrain profiles with different travel times and energy costs;
- continuous encoding progress;
- continuous data corruption;
- limited onboard memory;
- a fixed 40-unit battery;
- collection, movement, arrival, encoding-completion, data-loss, and offload events;
- validation of route metrics and battery use.

Movement is represented by an action, a continuous process, and an arrival event:

```text
start-move action
        |
        v
rover-travel process
        |
        v
arrive event
```

Battery is consumed only by movement. Encoding and corruption continue while the rover is travelling.

## Experimental design

The model was developed and checked with seeds `0-4`. After the configuration was frozen, the final experiment was run on unseen seeds `10-14`.

| Factor | Values |
|---|---|
| Dataset count | 2, 3, 4 |
| Memory level | low, medium, high |
| Memory ratio | 0.45, 0.70, 1.00 |
| Corruption level | low, medium, high |
| Final seeds | 10, 11, 12, 13, 14 |
| Battery capacity | 40 energy units |
| Terrain profiles | easy, moderate, rocky, steep |
| Planner | ENHSP `sat-hadd` |
| Standard timeout | 30 seconds |
| Classification timeout | 120 seconds |
| Final instances | 135 |

The 135 missions come from:

```text
3 dataset counts
x 3 memory levels
x 3 corruption levels
x 5 final seeds
= 135 missions
```

### Timeout handling

The original 30-second runs are kept for runtime analysis. Only the three timeout cases were rerun with a 120-second limit to obtain a final solved or unsolvable label.

| Outcome | Standard 30-second run | Final classification |
|---|---:|---:|
| Solved | 107 | 108 |
| Unsolvable | 25 | 27 |
| Timeout | 3 | 0 |

A timeout is not treated as evidence that a mission is unsolvable.

## Main results

### Mission success by factor

<p align="center">
  <img src="experiments/plots/battery_final/success_rates_wilson_95.png" width="74%" alt="Mission success with Wilson intervals">
</p>

Mission success decreased as the workload increased:

| Dataset count | Solved | Unsolvable | Success rate |
|---:|---:|---:|---:|
| 2 | 45 | 0 | 100% |
| 3 | 36 | 9 | 80% |
| 4 | 27 | 18 | 60% |

Memory showed the strongest feasibility effect:

| Memory level | Solved | Unsolvable | Success rate |
|---|---:|---:|---:|
| Low | 21 | 24 | 46.7% |
| Medium | 42 | 3 | 93.3% |
| High | 45 | 0 | 100% |

All three corruption levels produced an 80% success rate in the tested ranges.

### Interaction between mission size and memory

<p align="center">
  <img src="experiments/plots/battery_final/success_interaction_heatmap.png" width="66%" alt="Mission success across dataset count and memory">
</p>

The memory effect depends on mission size:

| Mission size | Low memory | Medium memory | High memory |
|---:|---:|---:|---:|
| 2 datasets | 100% | 100% | 100% |
| 3 datasets | 40% | 100% | 100% |
| 4 datasets | 0% | 80% | 100% |

Small missions do not reveal a storage bottleneck. As the number of datasets grows, limited memory forces extra returns to base and increases both energy use and exposure to data degradation.

### Planner runtime

<p align="center">
  <img src="experiments/plots/battery_final/runtime_summary_by_dataset_count.png" width="68%" alt="Planner runtime by dataset count">
</p>

| Dataset count | Median runtime | 90th percentile | Mean runtime |
|---:|---:|---:|---:|
| 2 | 0.384 s | 0.449 s | 0.398 s |
| 3 | 0.528 s | 1.755 s | 0.797 s |
| 4 | 7.315 s | 25.345 s | 9.358 s |

The increase from three to four datasets is substantial. All three standard timeouts occurred in four-dataset missions.

### Battery margin

<p align="center">
  <img src="experiments/plots/battery_final/battery_remaining_by_dataset_count.png" width="68%" alt="Battery remaining by dataset count">
</p>

Among solved missions, the average remaining battery fell from 21.73 units for two datasets to 8.44 units for three and 1.70 units for four. The largest solved missions therefore operated close to the 40-unit battery limit.

### Movement energy and makespan

<p align="center">
  <img src="experiments/plots/battery_final/energy_vs_makespan_scatter.png" width="68%" alt="Movement energy and generated-plan makespan">
</p>

Plans that use more movement energy generally also have a longer makespan because both quantities increase with travel. The planner is satisficing, so these values describe the generated plans and are not guaranteed global optima.

## Statistical summary

The notebook reports exploratory statistical tests and effect sizes:

- dataset count was associated with feasibility, with Cramer's V = 0.408;
- memory level had the strongest feasibility association, with Cramer's V = 0.593;
- corruption level showed no feasibility association in the final sample;
- dataset count had a large effect on standard planner runtime, with epsilon-squared = 0.750;
- matched missions showed large memory effects on movement, energy use, and makespan.

The complete tables are stored in:

```text
experiments/results/tables/battery_final/
```

## Repository structure

```text
planetary-rover-experimental-study/
├── experiments/
│   ├── config/
│   ├── scripts/
│   ├── results/
│   └── plots/
├── notebooks/
│   └── battery_rover_experiment_analysis.ipynb
├── paper/
│   ├── rover_planning_research_paper.tex
│   ├── rover_planning_research_paper.pdf
│   ├── references.bib
│   └── figures/
├── planning_models/
│   └── pddl_plus/
├── ros2_ws/
│   └── src/
└── README.md
```

Important files:

```text
planning_models/pddl_plus/domain-memory-rover-battery.pddl
experiments/config/experiment_config_battery.json
experiments/scripts/problem_generator.py
experiments/scripts/planner_runner.py
experiments/scripts/batch_experiment.py
experiments/results/battery_final_unseen.csv
experiments/results/battery_final_unseen_classified.csv
notebooks/battery_rover_experiment_analysis.ipynb
paper/rover_planning_research_paper.pdf
```

## Requirements

- Ubuntu 24.04 or WSL
- Python 3.12
- Java
- ENHSP
- ROS 2 Jazzy
- JupyterLab

Create the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install jupyterlab pandas numpy matplotlib scipy nbformat setuptools
```

## Generate one mission

```bash
python3 experiments/scripts/problem_generator.py \
  --model battery \
  --datasets 3 \
  --memory medium \
  --corruption medium \
  --seed 10 \
  --config experiments/config/experiment_config_battery.json \
  --output-dir experiments/generated_problems/example_battery_run
```

## Run ENHSP

```bash
python3 experiments/scripts/planner_runner.py \
  --domain planning_models/pddl_plus/domain-memory-rover-battery.pddl \
  --problem experiments/generated_problems/example_battery_run/rover-battery-n3-mem-medium-corr-medium-seed-10.pddl \
  --output experiments/raw_outputs/example_battery_run.txt \
  --planner sat-hadd \
  --timeout 30
```

## Reproduce the final batch

```bash
python3 experiments/scripts/batch_experiment.py \
  --model battery \
  --config experiments/config/experiment_config_battery.json \
  --runs-per-condition 5 \
  --seed-start 10 \
  --planner sat-hadd \
  --timeout 30 \
  --generated-dir experiments/generated_problems/battery_final_unseen \
  --raw-output-dir experiments/raw_outputs/battery_final_unseen \
  --results experiments/results/battery_final_unseen.csv
```

## Run the notebook

Start the ROS 2 service in one terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
export ROVER_PROJECT_ROOT="$PWD"
ros2 run rover_experiment_ros experiment_service
```

Start JupyterLab in another terminal:

```bash
source .venv/bin/activate
jupyter lab
```

Open:

```text
notebooks/battery_rover_experiment_analysis.ipynb
```

Then select:

```text
Kernel -> Restart Kernel and Run All Cells
```

The notebook validates the final data, generates the five main figures, performs the statistical tests, exports the result tables, and sends one ROS 2 request.

## ROS 2 interface

Build the workspace:

```bash
cd ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
cd ..
```

Run the service:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
export ROVER_PROJECT_ROOT="$PWD"
ros2 run rover_experiment_ros experiment_service
```

Send a request from a second terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash

ros2 run rover_experiment_ros experiment_client \
  --datasets 3 \
  --memory medium \
  --corruption medium \
  --seed 0 \
  --timeout 30
```

The response includes planner status, runtime, makespan, action counts, battery capacity, energy used, battery remaining, and battery feasibility.

## Paper

The final IEEE-style paper is available at:

```text
paper/rover_planning_research_paper.pdf
```

Build it from source with:

```bash
cd paper
./build_paper.sh
```

## Reproducibility

Mission generation is deterministic for the same dataset count, memory level, corruption level, seed, and configuration. Dataset properties, terrain, and corruption margins use separate deterministic random streams so that changing one factor does not regenerate unrelated mission properties.

The frozen final model is tagged:

```text
battery-model-frozen-v1
```

## Limitations

- The terrain map is a bidirectional line.
- Missions and terrain are synthetic.
- Data degradation is deterministic.
- Battery is consumed only by movement.
- One rover, one base, and one planner configuration are studied.
- Five unseen seeds are used per condition.
- Planner runtime includes Java and startup overhead.
- Generated plans are satisficing and are not guaranteed optimal.
- The project does not control a physical rover.

## Author

Endri Gjinaj  
Master's Degree in Robotics Engineering  
University of Genoa
