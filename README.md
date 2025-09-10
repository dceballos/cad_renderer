# CAD Renderer

A high-performance CAD rendering service for generating architectural drawings of windows and doors. Built with Python and Cairo graphics, this service produces SVG and PNG renderings with precise measurements, custom shapes, and detailed technical specifications.

## Features

- **Multiple Shape Support**: Renders various window/door shapes including rectangles, arches, circles, eyebrows, half-circles, octagons, quarter-circles, tombstones, trapezoids, and triangles
- **Top-View Rendering**: Generates architectural top-view drawings showing frame profiles and track systems
- **Muntin Patterns**: Supports complex muntin (grille) configurations with automatic labeling
- **Dynamic Scaling**: Automatically calculates optimal scale factors based on input dimensions
- **High-Quality Output**: Produces crisp vector graphics in SVG format or rasterized PNG images
- **RESTful API**: Simple HTTP POST endpoints for easy integration

## Prerequisites

- Python 3.9+
- Cairo graphics library
- Docker (optional, for containerized deployment)

## Installation

### Local Installation

1. Install system dependencies (Cairo):
   ```bash
   # On Ubuntu/Debian
   sudo apt-get install libcairo2-dev

   # On macOS
   brew install cairo

   # On Alpine Linux
   apk add cairo-dev cairo cairo-tools
   ```

2. Clone the repository:
   ```bash
   git clone https://github.com/dceballos/cad_renderer.git
   cd cad_renderer
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Docker Installation

Build and run using Docker Compose:
```bash
docker-compose up
```

For local development with volume mounting:
```bash
docker-compose -f local-compose.yml up
```

## Usage

### Starting the Server

Run the server locally:
```bash
python run.py
```

The server will start on `http://localhost:5002`

### API Endpoints

#### 1. Standard CAD Rendering - `/cad`

Renders a standard CAD drawing with the specified configuration.

**Request:**
```bash
POST /cad
Content-Type: application/json

{
  "width": 48,
  "height": 72,
  "shape": "arch",
  "panels": [...],
  "muntins": {...},
  "frame": {...}
}
```

**Response:** SVG or PNG file download

#### 2. Top-View Rendering - `/top-view`

Renders an architectural top-view drawing.

**Request:**
```bash
POST /top-view
Content-Type: application/json

{
  "width": 48,
  "height": 72,
  "frame_type": "sliding",
  "tracks": 2,
  "panels": [...]
}
```

**Response:** SVG or PNG file download

### Example Request

```python
import requests
import json

# CAD rendering request
data = {
    "width": 36,
    "height": 48,
    "shape": "rectangle",
    "panels": [
        {
            "type": "fixed",
            "width": 36,
            "height": 48,
            "muntin_pattern": "grid",
            "horizontal_bars": 2,
            "vertical_bars": 1
        }
    ],
    "scale": 10,
    "format": "svg"
}

response = requests.post('http://localhost:5002/cad', json=data)

# Save the rendered file
with open('window_rendering.svg', 'wb') as f:
    f.write(response.content)
```

## Project Structure

```
cad_renderer/
├── components/           # Core rendering components
│   ├── canvas.py        # Main rendering engine
│   ├── panel.py         # Panel layout management
│   ├── muntin.py        # Muntin bar rendering
│   ├── muntin_label.py  # Muntin dimension labels
│   ├── size_label.py    # Size annotation rendering
│   ├── utils.py         # Utility functions
│   ├── config.py        # Configuration constants
│   ├── shapes/          # Shape-specific renderers
│   │   ├── arch.py
│   │   ├── circle.py
│   │   ├── triangle.py
│   │   └── ...
│   ├── top_view/        # Top-view rendering logic
│   └── helpers/         # Helper utilities
├── services/            # Business logic services
│   └── normalization_service.py
├── enums/               # Enumerations and constants
│   └── colors.py
├── run.py               # Application entry point
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container configuration
└── compose.yml          # Docker Compose configuration
```

## Configuration

The service accepts various configuration parameters in the JSON request:

### Common Parameters
- `width`: Width of the window/door (in inches)
- `height`: Height of the window/door (in inches)
- `shape`: Shape type (rectangle, arch, circle, etc.)
- `scale`: Scale factor for rendering (default: auto-calculated)
- `format`: Output format (svg or png)
- `draw_label`: Whether to draw dimension labels (default: true)

### Panel Configuration
- `panels`: Array of panel configurations
- `type`: Panel type (fixed, sliding, casement, etc.)
- `muntin_pattern`: Grille pattern (grid, prairie, custom, etc.)
- `horizontal_bars`: Number of horizontal muntin bars
- `vertical_bars`: Number of vertical muntin bars

### Frame Configuration
- `frame_type`: Type of frame (standard, sliding, etc.)
- `frame_width`: Width of the frame
- `pocket_width`: Width of frame pockets (for sliding windows)

## Deployment

### Production Deployment

Use the provided deployment script to deploy to the production asset server:

```bash
./deploy-cad-renderer.sh
```

This script will:
1. Clone the repository from GitHub
2. Push to the production git server
3. Trigger the post-receive hook which:
   - Extracts code to a new release directory
   - Installs dependencies
   - Updates the current symlink
   - Restarts the cad-renderer service

### Docker Deployment

Build the production image:
```bash
docker build -t cad-renderer .
```

Run the container:
```bash
docker run -p 5002:5002 cad-renderer
```

## Development

### Running Tests

Currently, no automated tests are configured. Testing should be done manually by verifying rendered outputs.

### Code Style

The codebase follows standard Python conventions:
- PEP 8 style guide
- Type hints where applicable
- Descriptive variable and function names
- Modular component architecture

### Adding New Shapes

To add a new shape:

1. Create a new shape class in `components/shapes/`
2. Inherit from the base shape class
3. Implement the `draw()` method using Cairo context
4. Register the shape in `canvas.py`

Example:
```python
# components/shapes/custom_shape.py
class CustomShape:
    def __init__(self, x, y, width, height, context):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.context = context
    
    def draw(self):
        # Cairo drawing commands
        self.context.move_to(self.x, self.y)
        self.context.line_to(...)
        self.context.stroke()
```

## Performance Considerations

- **Memory Limit**: Request body size limited to 16MB
- **Temporary Files**: Rendered files are stored in `/tmp/` with random names
- **Caching**: No built-in caching; implement at proxy/CDN level if needed
- **Concurrency**: Thread-safe for handling multiple simultaneous requests

## Troubleshooting

### Cairo Installation Issues

If you encounter Cairo installation problems:

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install libcairo2-dev pkg-config python3-dev
```

**macOS:**
```bash
brew install cairo pkg-config
```

### Memory Issues

If rendering large or complex drawings causes memory issues:
- Reduce the scale factor
- Simplify muntin patterns
- Use SVG format instead of PNG for better memory efficiency

### Docker Issues

If the Docker container fails to start:
1. Ensure Cairo dependencies are properly installed in the Dockerfile
2. Check that port 5002 is not already in use
3. Verify volume mounts in local-compose.yml

## API Response Codes

- `200 OK`: Successful rendering, file returned
- `400 Bad Request`: Invalid input parameters
- `500 Internal Server Error`: Rendering error or system failure

## License

This project is proprietary software. All rights reserved.

## Support

For issues or questions, please contact the development team or create an issue in the GitHub repository.

## Acknowledgments

- Built with [Bottle](https://bottlepy.org/) web framework
- Rendering powered by [Cairo Graphics](https://www.cairographics.org/)
- Containerization with [Docker](https://www.docker.com/)