# 🏙️ Jakarta Barat Smart City Intelligence

**A Web GIS dashboard for exploring urban density, spatial activity, green space, and vehicle detection in West Jakarta, Indonesia.**

[![Python](https://img.shields.io/badge/Python-3.x-blue)](https://www.python.org/) [![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)](https://streamlit.io/) [![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)

🌐 **Live dashboard:** [jakbar-smartcity.perdananda.net](https://jakbar-smartcity.perdananda.net/)

> **Academic prototype — MCE302 (Smart City).** This dashboard supports exploratory analysis and does not represent official findings or policy decisions of the Jakarta government.

## Overview

Jakarta Barat Smart City Intelligence brings together selected public and locally prepared spatial datasets in a single interactive dashboard. The project explores how population density, OpenStreetMap (OSM) building footprints, green-space tags, points of interest (POIs), and vehicle detection can inform urban-planning discussions at the district (*kecamatan*) level.

The application is built with **Python and Streamlit**, uses **Folium** and **Plotly** for visualization, and is packaged with **Docker**.

## Features

| Module | Description |
| --- | --- |
| **Overview** | District-level map, POI distribution, building counts, building footprint coverage, green-space indicators, and available population-density information. |
| **Density Overview** | Compares population density across West Jakarta districts using imported population figures and area calculated from locally available OSM boundaries. |
| **Policy Recommendation** | Generates indicative investigation priorities using explicit heuristic rules based on available density, building, green-space, and POI indicators. |
| **POI & Mobility** | Maps POIs, filters categories, displays clustered markers, and visualizes spatial concentration through a heatmap. |
| **Urban Green Space** | Displays available building and land-use polygons and reports OSM-derived coverage metrics. |
| **CCTV & YOLO** | Accepts a manually uploaded image and runs CPU-based YOLO11n vehicle detection for cars, motorcycles, buses, and trucks. |
| **Sources & Methodology** | Explains data provenance, analytical assumptions, privacy considerations, and limitations. |

### Vehicle density score

The prototype computes an **illustrative heuristic score** from detected vehicle counts:

```text
score = cars + 0.5 × motorcycles + 2 × (buses + trucks)
```

This score is **not** an official traffic-congestion index. Detection from a single image does not measure vehicle flow per hour or establish live road conditions.

## Technology stack

- **Application:** Python, Streamlit, Pandas, NumPy
- **Maps and visualization:** OpenStreetMap, Folium, Streamlit-Folium, Plotly
- **Geospatial processing:** Shapely and local GeoJSON/OSM-derived datasets
- **Computer vision:** Ultralytics YOLO11n, Pillow
- **Deployment:** Docker, Docker Compose, VPS

## Project structure

```text
jakbar-smartcity/
├── app.py                # Streamlit dashboard
├── official_data.py      # Population-data handling and density calculations
├── osm_data.py           # OSM and GeoJSON processing
├── policy.py             # Heuristic policy recommendations
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker image definition
├── compose.yaml          # Deployment configuration (review before publishing)
├── data/                 # Local datasets/cache (not all committed)
└── models/               # Optional model assets
```

## Getting started

### Prerequisites

- Docker and Docker Compose, or a suitable Python environment
- Required local GIS datasets for the modules you intend to use
- Access to the YOLO11n weights for the vehicle-detection module

### Run with Docker Compose

Review `compose.yaml` for volume mounts, image/build settings, and port mappings before starting:

```bash
docker compose up -d --build
```

The Streamlit service listens on port `8501` inside the container. The public endpoint, if used, should be exposed through a properly configured HTTPS reverse proxy rather than exposing an unprotected application port.

### Run with Python

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Some visualizations require locally prepared data files. The repository may intentionally exclude large GIS datasets, model weights, and operational caches.

## Data and methodology

- **Administrative boundaries and spatial features:** OpenStreetMap-derived data, subject to mapping completeness and the availability of local files.
- **Population:** Imported administrative population data, when available and validated.
- **Population density:** Imported population count divided by the area computed from local OSM boundary geometry; this is **not necessarily the official BPS administrative area**.
- **Building coverage:** Building footprint area relative to the mapped district boundary.
- **Green coverage:** Coverage based on mapped OSM green-space/land-use tags, **not** satellite-derived vegetation segmentation.
- **POI heatmap:** Visualizes the concentration of mapped facilities; it is **not IDW interpolation** and does not indicate real-time congestion.
- **Policy recommendations:** Exploratory, rule-based outputs requiring data-quality checks and field validation.

**Current scope:** IDW interpolation, automatic live CCTV streaming, and a validated traffic-congestion prediction model are **not implemented** in this version.

## Security and privacy

The public dashboard is intended primarily for **read-only exploration**. Dataset synchronization and public GIS/CSV upload controls have been disabled in the deployed configuration. Vehicle-image upload remains an experimental feature and should be protected with file validation, request/resource limits, and appropriate privacy controls.

Images may contain faces or license plates. Only use images you are authorized to process, avoid publishing identifying details, and observe applicable Indonesian personal-data-protection requirements.

Do not commit API keys, credentials, private server addresses, production `.env` files, or sensitive datasets to this repository.

## Limitations

- OpenStreetMap completeness varies by location and feature type.
- Missing datasets can affect district comparisons and policy suggestions.
- Building footprint coverage is not equivalent to population density.
- A single CCTV snapshot cannot establish traffic flow or congestion trends.
- Results are educational and should not be used as standalone operational policy decisions.

## Academic context

Developed as a prototype for **MCE302 — Smart City**, focusing on spatial analytics and data-driven urban planning in West Jakarta.

## Attribution

© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Other dataset sources and their usage conditions should be credited individually when added to the repository.
