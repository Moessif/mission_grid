# MissionGrid Tauri Migration Design Spec

## [S1] Problem

Current PySide6 desktop application for drone mission planning has functional features but outdated UI. Need to migrate to modern web-based stack (Tauri + React + MUI v6) with Material You design language and smooth animations, while preserving all existing functionality and output compatibility.

## [S2] Architecture

### Tech Stack
- **Tauri 2.x**: Rust backend, WebView2 frontend
- **React 18 + TypeScript**: UI framework
- **MUI v6 (@mui/material)**: Material You components
- **Framer Motion**: Animation library
- **Zustand**: State management
- **Vite**: Build tool

### Directory Structure
```
mission-grid-tauri/
├── src-tauri/                    # Rust backend
│   ├── src/
│   │   ├── commands.rs           # Tauri commands (file I/O, export)
│   │   ├── mavlink.rs            # MAVLink UDP telemetry
│   │   └── main.rs
│   ├── Cargo.toml
│   └── tauri.conf.json
│
├── src/                          # React frontend
│   ├── App.tsx                   # MUI ThemeProvider + layout
│   ├── components/
│   │   ├── GridBoard.tsx         # 9x7 grid (CSS Grid + SVG overlay)
│   │   ├── ActionEditor.tsx      # Action editor dialog
│   │   ├── MainTaskEditor.tsx    # Main task editor dialog
│   │   ├── Toolbar.tsx           # Top toolbar
│   │   ├── SidePanel.tsx         # Right panel (Tabs)
│   │   └── FlightSimulation.tsx  # Flight simulation animation
│   ├── hooks/
│   │   └── useGridStore.ts       # Zustand global state
│   ├── utils/
│   │   ├── pathPlanner.ts        # TSP + BFS path planning
│   │   └── codeGenerator.ts      # Mission script generation
│   ├── types.ts                  # GridConfig, CellAction type definitions
│   └── main.tsx
│
├── package.json
└── vite.config.ts
```

### State Management
Zustand store holds entire `GridConfig` state. Components subscribe via selectors for minimal re-renders.

### Grid Rendering
CSS Grid layout for 9x7 cells. SVG overlay for path lines and drone position. Cells are `motion.div` with hover/press animations.

### Rust Backend Responsibilities
1. File I/O (save/load JSON, export mission bundle)
2. MAVLink UDP send/receive (`tokio::net::UdpSocket` + `mavlink` crate)

## [S3] Design System

### Theme
```typescript
const theme = createTheme({
  palette: {
    primary: { main: '#6750A4' },      // Material You purple
    secondary: { main: '#625B71' },
    background: { default: '#FFFBFE', paper: '#FFFBFE' },
  },
  shape: { borderRadius: 16 },
  typography: { fontFamily: '"Noto Sans SC", "Roboto", sans-serif' },
});
```

### Grid Visual Design
- Cell: 16px rounded card, `motion.div` + `whileHover` scale 1.05
- Action cell: Primary color fill + subtle shadow
- No-fly zone: Red semi-transparent + diagonal stripes
- Main task: Orange border pulse animation
- Takeoff point: Green breathing glow
- Path line: SVG `stroke-dasharray` progressive draw animation
- Drone position: Red circle + trail effect

### Dialogs
MUI `Dialog` + `Slide` transition, content uses `motion.div` stagger animation.

### Flight Simulation
Drone moves along path with smooth `framer-motion` animation, action cells trigger toast cards.

## [S4] Data Model

### TypeScript Types
```typescript
interface CellAction {
  actionType: string;
  params: Record<string, any>;
  triggers: string[];
}

interface GridConfig {
  cols: 9;
  rows: 7;
  cellSize: 0.5;
  takeoffCol: number;
  takeoffRow: number;
  flightAltitude: number;
  actions: Record<string, CellAction[]>;
  noFly: Set<string>;
  mainTaskCells: Set<string>;
  mainTaskConditions: string[];
  customWaypoints: [number, number][];
  fenceMinX: number;
  fenceMaxX: number;
  fenceMinY: number;
  fenceMaxY: number;
}
```

### Serialization
JSON format compatible with existing PySide6 version. Sets serialize as arrays.

## [S5] Path Planning

Port existing algorithms to TypeScript:
- BFS 8-directional pathfinding with diagonal safety check
- Distance matrix construction
- TSP solving: greedy + 2-opt heuristic (sufficient for ≤20 waypoints)
- Serpentine traversal for "visit all cells" mode

## [S6] Code Generation

String template generation, output format identical to existing version:
- `generated_mission.py` — unchanged
- `run_mission.sh` — unchanged
- `mission_config.json` — unchanged

## [S7] Rust Backend

### Tauri Commands
- `save_plan(path, data)` / `load_plan(path)` — JSON file read/write
- `export_mission(path, script_content, shell_content, json_content)` — write mission bundle files
- `start_mavlink(port)` / `stop_mavlink()` — UDP telemetry lifecycle
- `send_heartbeat()` — heartbeat send

### Communication
Frontend calls Rust via `invoke()`. Telemetry data pushed to frontend via Tauri `emit()` events.

## [S8] Feature Parity Checklist

| Feature | PySide6 | Tauri |
|---------|---------|-------|
| 9x7 grid visualization | QGraphicsView | CSS Grid + motion.div |
| Action editing (10 types) | QDialog | MUI Dialog |
| Trigger conditions (4 types) | Checkboxes | MUI Checkbox |
| Main task editor | QDialog | MUI Dialog |
| Global conditions (5 types) | Checkboxes | MUI Checkbox |
| No-fly zones | Right-click toggle | Right-click toggle |
| Manual waypoints | Click mode | Click mode |
| Path planning (2 modes) | python-tsp + BFS | greedy + 2-opt + BFS |
| Flight simulation | QTimer step | Framer Motion |
| Export mission bundle | File dialog | Tauri dialog + fs |
| Save/Load plan | JSON file | JSON file (compatible) |
| MAVLink telemetry | pymavlink QThread | Rust tokio + emit |
| ROS node monitor | Table | MUI Table |
| Data monitor | Table | MUI Table |
| Camera tab (placeholder) | Label | MUI Card |
| Point cloud tab (placeholder) | Label | MUI Card |

## [S9] Migration Compatibility

- JSON plan files: Bidirectional compatible (can load PySide6 saves in Tauri, and vice versa)
- Exported mission scripts: Identical output format
- Coordinate system: Same (A1-A9, B1-B7, origin at A9B1, 0.5m cells)
- All action types preserved with same parameters
