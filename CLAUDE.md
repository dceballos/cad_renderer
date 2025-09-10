# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Instructions

- When making git commits, do not add "Co-Authored-By: Claude" or similar attribution lines

## Development Commands

### Running the Application
```bash
# Run locally with Python
python run.py

# Run with Docker Compose
docker-compose -f local-compose.yml up

# Run production Docker build
docker-compose up
```

### Deployment
```bash
# Deploy to production asset server
./deploy-cad-renderer.sh
```

## Architecture Overview

This is a CAD rendering service built with Python that generates SVG/PNG images of windows and doors with custom shapes and configurations.

### Core Components

- **Web Server**: Bottle framework running on port 5002 with two main endpoints:
  - `/cad` - Renders standard CAD drawings
  - `/top-view` - Renders top-view perspectives

- **Canvas System** (`components/canvas.py`): Main rendering engine using Cairo library for vector graphics. Handles scaling, positioning, and coordinates all drawing components.

- **Shape Components** (`components/shapes/`): Individual shape classes for different window/door geometries:
  - Arch, Circle, Eyebrow, HalfCircle, Octagon, QuarterCircle, Tombstone, Trapezoid, Triangle
  - Each shape implements its own drawing logic using Cairo context

- **Panel System** (`components/panel.py`): Manages panel layouts, subdivisions, and muntin bar configurations within shapes.

- **Muntin Components** (`components/muntin.py`, `components/muntin_label.py`): Handles muntin bar drawing and labeling for window grilles.

- **Top View** (`components/top_view/`): Specialized rendering for architectural top-view drawings showing frame profiles and track systems.

- **Normalization Service** (`services/normalization_service.py`): Processes and normalizes input parameters before rendering.

### Key Technical Details

- **Cairo Graphics**: All rendering uses pycairo for vector graphics output
- **Dynamic Scaling**: Automatic scale factor calculation based on input dimensions
- **Temporary File Generation**: Renders to `/tmp/` with random filenames for concurrent request handling
- **Memory Limit**: Request body limited to 16MB for large CAD configurations

### Input Format

The service expects JSON input containing window/door specifications including:
- Dimensions (width, height)
- Shape type and parameters
- Panel configurations
- Muntin patterns
- Frame details
- Color and style options