# MissionGrid Tauri Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate PySide6 MissionGrid drone mission planner to Tauri 2 + React 18 + MUI v6 with Material You design and smooth animations.

**Architecture:** Tauri app with React frontend (Vite + TypeScript) for UI, Rust backend for file I/O and MAVLink UDP telemetry. State managed by Zustand. Grid rendered with CSS Grid + SVG overlay. Animations via Framer Motion.

**Tech Stack:** Tauri 2, React 18, TypeScript, MUI v6, Framer Motion, Zustand, Vite, Rust (tokio, mavlink)

## Global Constraints

- UI language: Chinese (zh-CN)
- Theme: Material You blue-purple (#6750A4 primary)
- Grid: 9 columns (A1-A9), 7 rows (B1-B7), 0.5m cells
- Coordinate origin: A9B1 (col=8, row=0)
- JSON plan format: Bidirectional compatible with PySide6 version
- Export format: Identical Python/Shell/JSON output
- Node.js >= 18, Rust stable
- No automated tests (no existing test infrastructure, hardware-dependent verification)

---

### Task 1: Project Scaffolding

**Covers:** S1, S2

**Files:**
- Create: `mission-grid-tauri/` (entire project directory)
- Create: `mission-grid-tauri/package.json`
- Create: `mission-grid-tauri/vite.config.ts`
- Create: `mission-grid-tauri/tsconfig.json`
- Create: `mission-grid-tauri/src/main.tsx`
- Create: `mission-grid-tauri/src/App.tsx`
- Create: `mission-grid-tauri/src/index.html`
- Create: `mission-grid-tauri/src-tauri/Cargo.toml`
- Create: `mission-grid-tauri/src-tauri/tauri.conf.json`
- Create: `mission-grid-tauri/src-tauri/src/main.rs`

**Interfaces:**
- Produces: Working Tauri dev shell with React rendering "Hello World"

- [ ] **Step 1: Create Tauri + React + Vite project**

Run from `D:\00Ai\Agents\MimoCode\workspace\ticup`:
```bash
npm create tauri-app@latest mission-grid-tauri -- --template react-ts
cd mission-grid-tauri
npm install
```

- [ ] **Step 2: Install frontend dependencies**

```bash
cd mission-grid-tauri
npm install @mui/material @mui/icons-material @emotion/react @emotion/styled framer-motion zustand
```

- [ ] **Step 3: Configure Vite**

Write `mission-grid-tauri/vite.config.ts`:
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    target: ["es2021", "chrome100", "safari13"],
    minify: !process.env.TAURI_DEBUG ? "esbuild" : false,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
});
```

- [ ] **Step 4: Configure Tauri**

Write `mission-grid-tauri/src-tauri/tauri.conf.json`:
```json
{
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devUrl": "http://localhost:1420",
    "target": "../dist"
  },
  "package": {
    "productName": "MissionGrid",
    "version": "1.0.0"
  },
  "tauri": {
    "allowlist": {
      "dialog": { "all": true },
      "fs": { "all": true },
      "shell": { "all": true }
    },
    "bundle": {
      "active": true,
      "identifier": "com.missiongrid.app",
      "icon": []
    },
    "security": {
      "csp": null
    },
    "windows": [
      {
        "title": "MissionGrid - 网格任务编排",
        "width": 1400,
        "height": 900,
        "resizable": true,
        "fullscreen": false
      }
    ]
  }
}
```

- [ ] **Step 5: Set up App.tsx with MUI ThemeProvider**

Write `mission-grid-tauri/src/App.tsx`:
```tsx
import { ThemeProvider, createTheme, CssBaseline } from "@mui/material";

const theme = createTheme({
  palette: {
    primary: { main: "#6750A4" },
    secondary: { main: "#625B71" },
    background: { default: "#FFFBFE", paper: "#FFFBFE" },
  },
  shape: { borderRadius: 16 },
  typography: { fontFamily: '"Noto Sans SC", "Roboto", sans-serif' },
});

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <div style={{ padding: 24 }}>
        <h1>MissionGrid</h1>
        <p>网格任务编排地面站</p>
      </div>
    </ThemeProvider>
  );
}
```

- [ ] **Step 6: Verify dev server runs**

```bash
cd mission-grid-tauri
npm run tauri dev
```
Expected: Window opens showing "MissionGrid" title with Material You theme.

---

### Task 2: Type Definitions & Zustand Store

**Covers:** S4

**Files:**
- Create: `mission-grid-tauri/src/types.ts`
- Create: `mission-grid-tauri/src/hooks/useGridStore.ts`

**Interfaces:**
- Produces: `GridConfig`, `CellAction`, `TRIGGER_CONDITIONS`, `MAIN_TASK_GLOBAL_CONDITIONS`, `ACTION_TYPES` types and constants
- Produces: `useGridStore` Zustand store with all state and actions

- [ ] **Step 1: Create type definitions**

Write `mission-grid-tauri/src/types.ts`:
```typescript
export const COLS = 9;
export const ROWS = 7;
export const CELL_SIZE = 0.5;

export const COL_LABELS = Array.from({ length: COLS }, (_, i) => `A${i + 1}`);
export const ROW_LABELS = Array.from({ length: ROWS }, (_, i) => `B${i + 1}`);

export const TRIGGER_CONDITIONS = [
  { id: "always", label: "每次经过" },
  { id: "first_visit", label: "首次经过" },
  { id: "last_visit", label: "最后经过" },
  { id: "main_task_done", label: "主线完成后" },
] as const;

export const MAIN_TASK_GLOBAL_CONDITIONS = [
  { id: "all_visited", label: "所有格子已遍历" },
  { id: "all_actions_done", label: "所有非降落动作已执行" },
  { id: "all_detect_done", label: "所有动物检测已完成" },
  { id: "all_qr_done", label: "所有二维码已扫描" },
  { id: "all_photo_done", label: "所有拍照已完成" },
] as const;

export interface CellAction {
  actionType: string;
  params: Record<string, any>;
  triggers: string[];
}

export const ACTION_TYPES = [
  { id: "takeoff", label: "起飞", defaultParams: { altitude: 1.2 } },
  { id: "photo", label: "拍照保存", defaultParams: { save_dir: "/home/orangepi/Desktop/captures", prefix: "photo" } },
  { id: "qr_scan", label: "识别二维码", defaultParams: { save_dir: "/home/orangepi/Desktop/qr_results" } },
  { id: "yolo_detect", label: "YOLO动物识别", defaultParams: { model_path: "/home/orangepi/ctrl_ws/src/competition_pkg/scripts/animal82.onnx", save_dir: "/home/orangepi/Desktop/yolo_results", confidence: 0.6 } },
  { id: "h_land", label: "识别H点降落", defaultParams: {} },
  { id: "land", label: "直接降落", defaultParams: {} },
  { id: "set_yaw", label: "调整航向", defaultParams: { yaw_deg: 90.0 } },
  { id: "buzzer", label: "蜂鸣器", defaultParams: { audio_id: 1 } },
  { id: "servo", label: "舵机", defaultParams: { servo_id: 1, open_servo: true } },
  { id: "laser", label: "激光", defaultParams: { laser_on: true, duration_sec: 0.5 } },
] as const;

export interface GridConfig {
  cols: number;
  rows: number;
  cellSize: number;
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

export function cellKey(col: number, row: number): string {
  return `${col},${row}`;
}

export function cellLabel(col: number, row: number): string {
  return `${COL_LABELS[col]}${ROW_LABELS[row]}`;
}

export function gridToXY(col: number, row: number): [number, number] {
  return [(COLS - 1 - col) * CELL_SIZE, row * CELL_SIZE];
}
```

- [ ] **Step 2: Create Zustand store**

Write `mission-grid-tauri/src/hooks/useGridStore.ts`:
```typescript
import { create } from "zustand";
import { CellAction, COLS, ROWS, CELL_SIZE, GridConfig, cellKey } from "../types";

interface GridState extends GridConfig {
  setAction: (col: number, row: number, actions: CellAction[]) => void;
  toggleNoFly: (col: number, row: number) => void;
  toggleMainTask: (col: number, row: number) => void;
  setMainTaskCells: (cells: Set<string>) => void;
  setMainTaskConditions: (conditions: string[]) => void;
  addWaypoint: (col: number, row: number) => void;
  removeWaypoint: (col: number, row: number) => void;
  clearWaypoints: () => void;
  setFlightAltitude: (alt: number) => void;
  setFence: (minX: number, maxX: number, minY: number, maxY: number) => void;
  setTakeoff: (col: number, row: number) => void;
  updateTakeoffFromActions: () => void;
  loadPlan: (data: any) => void;
  reset: () => void;
}

const defaultState = {
  cols: COLS,
  rows: ROWS,
  cellSize: CELL_SIZE,
  takeoffCol: 8,
  takeoffRow: 0,
  flightAltitude: 1.2,
  actions: {} as Record<string, CellAction[]>,
  noFly: new Set<string>(),
  mainTaskCells: new Set<string>(),
  mainTaskConditions: [] as string[],
  customWaypoints: [] as [number, number][],
  fenceMinX: 0,
  fenceMaxX: 4,
  fenceMinY: 0,
  fenceMaxY: 3,
};

export const useGridStore = create<GridState>((set, get) => ({
  ...defaultState,

  setAction: (col, row, actions) => set((s) => {
    const key = cellKey(col, row);
    const next = { ...s.actions };
    if (actions.length > 0) {
      next[key] = actions;
    } else {
      delete next[key];
    }
    return { actions: next };
  }),

  toggleNoFly: (col, row) => set((s) => {
    const key = cellKey(col, row);
    const next = new Set(s.noFly);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
      const actions = { ...s.actions };
      delete actions[key];
      return { noFly: next, actions };
    }
    return { noFly: next };
  }),

  toggleMainTask: (col, row) => set((s) => {
    const key = cellKey(col, row);
    const next = new Set(s.mainTaskCells);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return { mainTaskCells: next };
  }),

  setMainTaskCells: (cells) => set({ mainTaskCells: cells }),
  setMainTaskConditions: (conditions) => set({ mainTaskConditions: conditions }),

  addWaypoint: (col, row) => set((s) => ({
    customWaypoints: [...s.customWaypoints, [col, row]],
  })),

  removeWaypoint: (col, row) => set((s) => ({
    customWaypoints: s.customWaypoints.filter(([c, r]) => c !== col || r !== row),
  })),

  clearWaypoints: () => set({ customWaypoints: [] }),

  setFlightAltitude: (alt) => set({ flightAltitude: alt }),

  setFence: (minX, maxX, minY, maxY) => set({
    fenceMinX: minX, fenceMaxX: maxX, fenceMinY: minY, fenceMaxY: maxY,
  }),

  setTakeoff: (col, row) => set({ takeoffCol: col, takeoffRow: row }),

  updateTakeoffFromActions: () => {
    const { actions } = get();
    for (const [key, actionList] of Object.entries(actions)) {
      if (actionList.some((a) => a.actionType === "takeoff")) {
        const [col, row] = key.split(",").map(Number);
        set({ takeoffCol: col, takeoffRow: row });
        return;
      }
    }
    set({ takeoffCol: 8, takeoffRow: 0 });
  },

  loadPlan: (data) => set({
    takeoffCol: data.takeoff_col ?? 8,
    takeoffRow: data.takeoff_row ?? 0,
    flightAltitude: data.flight_altitude ?? 1.2,
    fenceMinX: data.fence_min_x ?? 0,
    fenceMaxX: data.fence_max_x ?? 4,
    fenceMinY: data.fence_min_y ?? 0,
    fenceMaxY: data.fence_max_y ?? 3,
    actions: Object.fromEntries(
      Object.entries(data.actions ?? {}).map(([k, v]: [string, any]) => [
        k,
        (v as any[]).map((a) => ({
          actionType: a.type,
          params: a.params ?? {},
          triggers: a.triggers ?? ["always"],
        })),
      ])
    ),
    noFly: new Set(data.no_fly ?? []),
    mainTaskCells: new Set(data.main_task_cells ?? []),
    mainTaskConditions: data.main_task_conditions ?? [],
    customWaypoints: (data.custom_waypoints ?? []).map((s: string) => {
      const [c, r] = s.split(",").map(Number);
      return [c, r] as [number, number];
    }),
  }),

  reset: () => set(defaultState),
}));
```

- [ ] **Step 3: Verify store works**

Add a quick test in App.tsx:
```tsx
import { useGridStore } from "./hooks/useGridStore";
// In App component:
const altitude = useGridStore((s) => s.flightAltitude);
<p>飞行高度: {altitude}m</p>
```
Run `npm run tauri dev` — should display "飞行高度: 1.2m".

---

### Task 3: Grid Board Visualization

**Covers:** S3

**Files:**
- Create: `mission-grid-tauri/src/components/GridBoard.tsx`

**Interfaces:**
- Consumes: `useGridStore` (actions, noFly, mainTaskCells, customWaypoints, takeoffCol, takeoffRow)
- Produces: `GridBoard` component with click/right-click handlers

- [ ] **Step 1: Create GridBoard component**

Write `mission-grid-tauri/src/components/GridBoard.tsx`:
```tsx
import { Box, Typography, Paper } from "@mui/material";
import { motion } from "framer-motion";
import { useGridStore } from "../hooks/useGridStore";
import { COLS, ROWS, COL_LABELS, ROW_LABELS, cellKey, cellLabel, ACTION_TYPES } from "../types";

const CELL_PX = 64;

function getCellColor(col: number, row: number, state: ReturnType<typeof useGridStore.getState>): string {
  const key = cellKey(col, row);
  if (col === state.takeoffCol && row === state.takeoffRow) return "#4CAF50";
  if (state.noFly.has(key)) return "#F44336";
  if (state.mainTaskCells.has(key)) return "#FF9800";
  if (state.actions[key]?.length > 0) return "#6750A4";
  return "#F5F5F5";
}

function getCellActions(col: number, row: number, actions: Record<string, any[]>): string[] {
  const key = cellKey(col, row);
  return (actions[key] ?? []).map((a) => {
    const type = ACTION_TYPES.find((t) => t.id === a.actionType);
    return type?.label ?? a.actionType;
  });
}

export default function GridBoard({
  onCellClick,
  onCellRightClick,
}: {
  onCellClick: (col: number, row: number) => void;
  onCellRightClick: (col: number, row: number) => void;
}) {
  const actions = useGridStore((s) => s.actions);
  const noFly = useGridStore((s) => s.noFly);
  const mainTaskCells = useGridStore((s) => s.mainTaskCells);
  const takeoffCol = useGridStore((s) => s.takeoffCol);
  const takeoffRow = useGridStore((s) => s.takeoffRow);
  const customWaypoints = useGridStore((s) => s.customWaypoints);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", p: 2 }}>
      {/* Column headers */}
      <Box sx={{ display: "grid", gridTemplateColumns: `40px repeat(${COLS}, ${CELL_PX}px)`, gap: "4px", mb: 1 }}>
        <Box />
        {COL_LABELS.map((label) => (
          <Typography key={label} variant="caption" align="center" fontWeight="bold">{label}</Typography>
        ))}
      </Box>

      {/* Grid rows */}
      {Array.from({ length: ROWS }, (_, row) => ROWS - 1 - row).map((row) => (
        <Box key={row} sx={{ display: "grid", gridTemplateColumns: `40px repeat(${COLS}, ${CELL_PX}px)`, gap: "4px", mb: "4px" }}>
          <Typography variant="caption" sx={{ display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>
            {ROW_LABELS[row]}
          </Typography>
          {Array.from({ length: COLS }, (_, col) => {
            const key = cellKey(col, row);
            const color = getCellColor(col, row, { actions, noFly, mainTaskCells, takeoffCol, takeoffRow } as any);
            const actionNames = getCellActions(col, row, actions);
            const isTakeoff = col === takeoffCol && row === takeoffRow;
            const isNoFly = noFly.has(key);
            const isMain = mainTaskCells.has(key);
            const wpIndex = customWaypoints.findIndex(([c, r]) => c === col && r === row);

            return (
              <motion.div
                key={col}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => onCellClick(col, row)}
                onContextMenu={(e) => { e.preventDefault(); onCellRightClick(col, row); }}
                style={{
                  width: CELL_PX,
                  height: CELL_PX,
                  borderRadius: 16,
                  backgroundColor: color,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  border: isMain ? "3px solid #FF9800" : isNoFly ? "2px dashed #F44336" : "1px solid #E0E0E0",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                {isTakeoff && (
                  <motion.div
                    animate={{ opacity: [0.3, 0.7, 0.3] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    style={{ position: "absolute", inset: 0, borderRadius: 16, background: "radial-gradient(circle, rgba(76,175,80,0.3) 0%, transparent 70%)" }}
                  />
                )}
                <Typography variant="caption" sx={{ fontSize: 9, color: color === "#F5F5F5" ? "#999" : "#fff", fontWeight: "bold", zIndex: 1 }}>
                  {cellLabel(col, row)}
                </Typography>
                {actionNames.length > 0 && (
                  <Typography variant="caption" sx={{ fontSize: 7, color: "#fff", zIndex: 1, textAlign: "center", lineHeight: 1.1, mt: 0.25 }}>
                    {actionNames.slice(0, 2).join(", ")}
                  </Typography>
                )}
                {wpIndex >= 0 && (
                  <Box sx={{ position: "absolute", top: 2, right: 4, fontSize: 10, fontWeight: "bold", color: "#FF9800", zIndex: 2 }}>
                    {wpIndex + 1}
                  </Box>
                )}
              </motion.div>
            );
          })}
        </Box>
      ))}
    </Box>
  );
}
```

- [ ] **Step 2: Wire GridBoard into App.tsx**

Update `App.tsx` to render GridBoard:
```tsx
import { useState } from "react";
import { ThemeProvider, createTheme, CssBaseline, Box } from "@mui/material";
import GridBoard from "./components/GridBoard";

const theme = createTheme({
  palette: {
    primary: { main: "#6750A4" },
    secondary: { main: "#625B71" },
    background: { default: "#FFFBFE", paper: "#FFFBFE" },
  },
  shape: { borderRadius: 16 },
  typography: { fontFamily: '"Noto Sans SC", "Roboto", sans-serif' },
});

export default function App() {
  const handleCellClick = (col: number, row: number) => {
    console.log(`Click: ${col},${row}`);
  };
  const handleCellRightClick = (col: number, row: number) => {
    console.log(`Right-click: ${col},${row}`);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: "flex", height: "100vh", bgcolor: "background.default" }}>
        <Box sx={{ flex: 1, overflow: "auto" }}>
          <GridBoard onCellClick={handleCellClick} onCellRightClick={handleCellRightClick} />
        </Box>
      </Box>
    </ThemeProvider>
  );
}
```

- [ ] **Step 3: Verify grid renders**

Run `npm run tauri dev`. Expected: 9×7 grid with colored cells, labels, hover animation. Right-click should toggle no-fly (red).

---

### Task 4: Action Editor Dialog

**Covers:** S4 (actions and triggers)

**Files:**
- Create: `mission-grid-tauri/src/components/ActionEditor.tsx`

**Interfaces:**
- Consumes: `useGridStore` (actions, setAction), `CellAction`, `ACTION_TYPES`, `TRIGGER_CONDITIONS`
- Produces: `ActionEditor` dialog component (open/close state managed externally)

- [ ] **Step 1: Create ActionEditor dialog**

Write `mission-grid-tauri/src/components/ActionEditor.tsx`:
```tsx
import { useState, useEffect } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, List, ListItem,
  ListItemButton, ListItemText, IconButton, Checkbox, FormControlLabel, FormGroup,
  Box, Typography, TextField, Select, MenuItem, FormControl, InputLabel, Chip,
} from "@mui/material";
import { Add, Delete } from "@mui/icons-material";
import { motion, AnimatePresence } from "framer-motion";
import { useGridStore } from "../hooks/useGridStore";
import { CellAction, ACTION_TYPES, TRIGGER_CONDITIONS, cellLabel } from "../types";

interface Props {
  open: boolean;
  col: number;
  row: number;
  onClose: () => void;
}

export default function ActionEditor({ open, col, row, onClose }: Props) {
  const storeActions = useGridStore((s) => s.actions);
  const setAction = useGridStore((s) => s.setAction);
  const key = `${col},${row}`;

  const [localActions, setLocalActions] = useState<CellAction[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    if (open) {
      setLocalActions(
        (storeActions[key] ?? []).map((a) => ({
          ...a,
          params: { ...a.params },
          triggers: [...a.triggers],
        }))
      );
      setSelectedIndex(0);
    }
  }, [open, key, storeActions]);

  const selected = localActions[selectedIndex];

  const addAction = () => {
    const type = ACTION_TYPES[0];
    setLocalActions((prev) => [
      ...prev,
      { actionType: type.id, params: { ...type.defaultParams }, triggers: ["always"] },
    ]);
    setSelectedIndex(localActions.length);
  };

  const deleteAction = () => {
    setLocalActions((prev) => prev.filter((_, i) => i !== selectedIndex));
    setSelectedIndex(Math.max(0, selectedIndex - 1));
  };

  const updateTrigger = (triggerId: string, checked: boolean) => {
    setLocalActions((prev) =>
      prev.map((a, i) => {
        if (i !== selectedIndex) return a;
        let triggers = checked
          ? [...a.triggers.filter((t) => t !== "always"), triggerId]
          : a.triggers.filter((t) => t !== triggerId);
        if (triggers.length === 0) triggers = ["always"];
        if (triggerId === "always" && checked) triggers = ["always"];
        return { ...a, triggers };
      })
    );
  };

  const updateParam = (key: string, value: any) => {
    setLocalActions((prev) =>
      prev.map((a, i) => (i === selectedIndex ? { ...a, params: { ...a.params, [key]: value } } : a))
    );
  };

  const handleSave = () => {
    setAction(col, row, localActions);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth
      TransitionProps={{ timeout: 300 }}>
      <DialogTitle>编辑动作 — {cellLabel(col, row)}</DialogTitle>
      <DialogContent sx={{ display: "flex", gap: 2, minHeight: 400 }}>
        {/* Left: action list */}
        <Box sx={{ width: 240, borderRight: "1px solid #eee", pr: 1 }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <IconButton onClick={addAction} size="small" color="primary"><Add /></IconButton>
            <IconButton onClick={deleteAction} size="small" color="error" disabled={localActions.length === 0}><Delete /></IconButton>
          </Box>
          <List dense>
            <AnimatePresence>
              {localActions.map((a, i) => {
                const type = ACTION_TYPES.find((t) => t.id === a.actionType);
                const triggerLabel = a.triggers.map((t) => TRIGGER_CONDITIONS.find((tc) => tc.id === t)?.label ?? t).join(", ");
                return (
                  <motion.div key={i} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                    <ListItemButton selected={i === selectedIndex} onClick={() => setSelectedIndex(i)}>
                      <ListItemText primary={type?.label ?? a.actionType} secondary={triggerLabel} />
                    </ListItemButton>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </List>
          {localActions.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: "center", mt: 2 }}>
              点击 + 添加动作
            </Typography>
          )}
        </Box>

        {/* Right: edit panel */}
        <Box sx={{ flex: 1 }}>
          {selected ? (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <FormControl size="small">
                <InputLabel>动作类型</InputLabel>
                <Select
                  value={selected.actionType}
                  label="动作类型"
                  onChange={(e) => {
                    const newType = ACTION_TYPES.find((t) => t.id === e.target.value)!;
                    setLocalActions((prev) =>
                      prev.map((a, i) => (i === selectedIndex ? { ...a, actionType: newType.id, params: { ...newType.defaultParams } } : a))
                    );
                  }}
                >
                  {ACTION_TYPES.map((t) => (
                    <MenuItem key={t.id} value={t.id}>{t.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              <Box>
                <Typography variant="subtitle2" gutterBottom>触发条件</Typography>
                <FormGroup row>
                  {TRIGGER_CONDITIONS.map((tc) => (
                    <FormControlLabel
                      key={tc.id}
                      control={<Checkbox checked={selected.triggers.includes(tc.id)} onChange={(e) => updateTrigger(tc.id, e.target.checked)} />}
                      label={tc.label}
                    />
                  ))}
                </FormGroup>
              </Box>

              <Box>
                <Typography variant="subtitle2" gutterBottom>参数</Typography>
                {Object.entries(selected.params).map(([k, v]) => (
                  <Box key={k} sx={{ mb: 1 }}>
                    {typeof v === "boolean" ? (
                      <FormControlLabel
                        control={<Checkbox checked={v} onChange={(e) => updateParam(k, e.target.checked)} />}
                        label={k}
                      />
                    ) : typeof v === "number" ? (
                      <TextField
                        label={k}
                        type="number"
                        value={v}
                        size="small"
                        fullWidth
                        onChange={(e) => updateParam(k, Number(e.target.value))}
                      />
                    ) : (
                      <TextField
                        label={k}
                        value={v}
                        size="small"
                        fullWidth
                        onChange={(e) => updateParam(k, e.target.value)}
                      />
                    )}
                  </Box>
                ))}
              </Box>
            </Box>
          ) : (
            <Typography color="text.secondary" sx={{ textAlign: "center", mt: 8 }}>
              选择或添加一个动作
            </Typography>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>取消</Button>
        <Button onClick={handleSave} variant="contained">确定</Button>
      </DialogActions>
    </Dialog>
  );
}
```

- [ ] **Step 2: Wire ActionEditor into App.tsx**

Update App.tsx to open ActionEditor on cell click:
```tsx
import { useState } from "react";
import ActionEditor from "./components/ActionEditor";

// In App component:
const [editorOpen, setEditorOpen] = useState(false);
const [editCell, setEditCell] = useState<[number, number]>([0, 0]);

const handleCellClick = (col: number, row: number) => {
  setEditCell([col, row]);
  setEditorOpen(true);
};

// Add to JSX:
<ActionEditor open={editorOpen} col={editCell[0]} row={editCell[1]} onClose={() => setEditorOpen(false)} />
```

- [ ] **Step 3: Verify action editor**

Run `npm run tauri dev`. Click a cell → dialog opens. Add action, edit triggers/params, save. Cell should show action name.

---

### Task 5: Main Task Editor Dialog

**Covers:** S4 (main task cells + global conditions)

**Files:**
- Create: `mission-grid-tauri/src/components/MainTaskEditor.tsx`

**Interfaces:**
- Consumes: `useGridStore` (actions, mainTaskCells, mainTaskConditions, setMainTaskCells, setMainTaskConditions)
- Produces: `MainTaskEditor` dialog component

- [ ] **Step 1: Create MainTaskEditor dialog**

Write `mission-grid-tauri/src/components/MainTaskEditor.tsx`:
```tsx
import { useState, useEffect } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button,
  Checkbox, FormControlLabel, FormGroup, Box, Typography, Divider, Chip,
} from "@mui/material";
import { useGridStore } from "../hooks/useGridStore";
import { ACTION_TYPES, MAIN_TASK_GLOBAL_CONDITIONS, cellLabel } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function MainTaskEditor({ open, onClose }: Props) {
  const actions = useGridStore((s) => s.actions);
  const storeCells = useGridStore((s) => s.mainTaskCells);
  const storeConditions = useGridStore((s) => s.mainTaskConditions);
  const setMainTaskCells = useGridStore((s) => s.setMainTaskCells);
  const setMainTaskConditions = useGridStore((s) => s.setMainTaskConditions);

  const [localCells, setLocalCells] = useState<Set<string>>(new Set());
  const [localConditions, setLocalConditions] = useState<string[]>([]);

  useEffect(() => {
    if (open) {
      setLocalCells(new Set(storeCells));
      setLocalConditions([...storeConditions]);
    }
  }, [open, storeCells, storeConditions]);

  const actionCellEntries = Object.entries(actions).map(([key, actionList]) => {
    const [col, row] = key.split(",").map(Number);
    const labels = actionList.map((a) => {
      const type = ACTION_TYPES.find((t) => t.id === a.actionType);
      return type?.label ?? a.actionType;
    });
    return { key, col, row, labels };
  });

  const nCells = localCells.size;
  const nConditions = localConditions.length;

  const handleSave = () => {
    setMainTaskCells(localCells);
    setMainTaskConditions(localConditions);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>编辑主线任务</DialogTitle>
      <DialogContent sx={{ minHeight: 400 }}>
        <Typography variant="subtitle2" gutterBottom>主线任务格子</Typography>
        <Box sx={{ maxHeight: 200, overflow: "auto", mb: 2 }}>
          {actionCellEntries.length === 0 ? (
            <Typography variant="body2" color="text.secondary">暂无动作格子，请先在网格上设置动作</Typography>
          ) : (
            actionCellEntries.map(({ key, col, row, labels }) => (
              <FormControlLabel
                key={key}
                control={
                  <Checkbox
                    checked={localCells.has(key)}
                    onChange={(e) => {
                      const next = new Set(localCells);
                      if (e.target.checked) next.add(key);
                      else next.delete(key);
                      setLocalCells(next);
                    }}
                  />
                }
                label={`${cellLabel(col, row)}  —  ${labels.join(", ")}`}
              />
            ))
          )}
        </Box>

        <Divider sx={{ my: 2 }} />

        <Typography variant="subtitle2" gutterBottom>全局完成条件</Typography>
        <FormGroup>
          {MAIN_TASK_GLOBAL_CONDITIONS.map((gc) => (
            <FormControlLabel
              key={gc.id}
              control={
                <Checkbox
                  checked={localConditions.includes(gc.id)}
                  onChange={(e) => {
                    setLocalConditions((prev) =>
                      e.target.checked ? [...prev, gc.id] : prev.filter((c) => c !== gc.id)
                    );
                  }}
                />
              }
              label={gc.label}
            />
          ))}
        </FormGroup>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
          满足所有勾选的全局条件时，触发"主线完成后"
        </Typography>
      </DialogContent>
      <DialogActions>
        <Chip label={`已选 ${nCells} 个格子, ${nConditions} 个条件`} sx={{ mr: "auto" }} />
        <Button onClick={onClose}>取消</Button>
        <Button onClick={handleSave} variant="contained">确定</Button>
      </DialogActions>
    </Dialog>
  );
}
```

- [ ] **Step 2: Wire into App.tsx**

```tsx
import MainTaskEditor from "./components/MainTaskEditor";
// State:
const [mainTaskOpen, setMainTaskOpen] = useState(false);
// JSX:
<MainTaskEditor open={mainTaskOpen} onClose={() => setMainTaskOpen(false)} />
```

---

### Task 6: Toolbar & Layout

**Covers:** S2

**Files:**
- Create: `mission-grid-tauri/src/components/Toolbar.tsx`
- Modify: `mission-grid-tauri/src/App.tsx` (full layout)

**Interfaces:**
- Consumes: `useGridStore` (flightAltitude, fence values, setFlightAltitude, setFence)
- Produces: `Toolbar` component, main layout with grid + right panel

- [ ] **Step 1: Create Toolbar component**

Write `mission-grid-tauri/src/components/Toolbar.tsx`:
```tsx
import { Box, TextField, Typography, Button, ButtonGroup, Tooltip } from "@mui/material";
import { AutoAwesome, FileDownload, FileUpload, Save, OpenInNew, PlayArrow } from "@mui/icons-material";
import { useGridStore } from "../hooks/useGridStore";

interface Props {
  onPlanPath: () => void;
  onExport: () => void;
  onSave: () => void;
  onLoad: () => void;
  onSimulate: () => void;
}

export default function Toolbar({ onPlanPath, onExport, onSave, onLoad, onSimulate }: Props) {
  const altitude = useGridStore((s) => s.flightAltitude);
  const setAltitude = useGridStore((s) => s.setFlightAltitude);
  const fenceMinX = useGridStore((s) => s.fenceMinX);
  const fenceMaxX = useGridStore((s) => s.fenceMaxX);
  const fenceMinY = useGridStore((s) => s.fenceMinY);
  const fenceMaxY = useGridStore((s) => s.fenceMaxY);
  const setFence = useGridStore((s) => s.setFence);

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 2, p: 1.5, bgcolor: "background.paper", borderBottom: "1px solid #eee", flexWrap: "wrap" }}>
      <Typography variant="body2" fontWeight="bold">飞行高度:</Typography>
      <TextField
        type="number"
        value={altitude}
        size="small"
        sx={{ width: 80 }}
        inputProps={{ step: 0.1, min: 0.3, max: 5 }}
        onChange={(e) => setAltitude(Number(e.target.value))}
      />
      <Typography variant="body2" fontWeight="bold">围栏 X:</Typography>
      <TextField type="number" value={fenceMinX} size="small" sx={{ width: 70 }} onChange={(e) => setFence(Number(e.target.value), fenceMaxX, fenceMinY, fenceMaxY)} />
      <Typography>-</Typography>
      <TextField type="number" value={fenceMaxX} size="small" sx={{ width: 70 }} onChange={(e) => setFence(fenceMinX, Number(e.target.value), fenceMinY, fenceMaxY)} />
      <Typography variant="body2" fontWeight="bold">Y:</Typography>
      <TextField type="number" value={fenceMinY} size="small" sx={{ width: 70 }} onChange={(e) => setFence(fenceMinX, fenceMaxX, Number(e.target.value), fenceMaxY)} />
      <Typography>-</Typography>
      <TextField type="number" value={fenceMaxY} size="small" sx={{ width: 70 }} onChange={(e) => setFence(fenceMinX, fenceMaxX, fenceMinY, Number(e.target.value))} />

      <Box sx={{ flex: 1 }} />

      <ButtonGroup variant="contained" size="small">
        <Tooltip title="自动规划路径">
          <Button startIcon={<AutoAwesome />} onClick={onPlanPath}>规划路径</Button>
        </Tooltip>
        <Tooltip title="导出任务包">
          <Button startIcon={<FileDownload />} onClick={onExport}>导出</Button>
        </Tooltip>
        <Tooltip title="模拟飞行">
          <Button startIcon={<PlayArrow />} onClick={onSimulate}>模拟</Button>
        </Tooltip>
      </ButtonGroup>
      <ButtonGroup variant="outlined" size="small">
        <Button startIcon={<Save />} onClick={onSave}>保存</Button>
        <Button startIcon={<OpenInNew />} onClick={onLoad}>加载</Button>
      </ButtonGroup>
    </Box>
  );
}
```

- [ ] **Step 2: Create full App layout**

Rewrite `App.tsx` with complete layout: left grid area + right side panel placeholder. Wire Toolbar, GridBoard, ActionEditor, MainTaskEditor together. Right panel will be expanded in Task 7.

---

### Task 7: Side Panel with Tabs

**Covers:** S2

**Files:**
- Create: `mission-grid-tauri/src/components/SidePanel.tsx`

**Interfaces:**
- Produces: `SidePanel` with tabs: ROS节点监控, 数据监控, 摄像头, 3D点云

- [ ] **Step 1: Create SidePanel component**

Write `mission-grid-tauri/src/components/SidePanel.tsx` with MUI Tabs, Tables for node/status monitoring, placeholder cards for camera/lidar.

---

### Task 8: Path Planning (TypeScript)

**Covers:** S5

**Files:**
- Create: `mission-grid-tauri/src/utils/pathPlanner.ts`

**Interfaces:**
- Consumes: `GridConfig` (actions, noFly, takeoffCol, takeoffRow)
- Produces: `planPath(config): [number, number][]` and `planPathAll(config): [number, number][]`

- [ ] **Step 1: Implement BFS pathfinding**

```typescript
function neighbors(col: number, row: number, config: GridConfig): [number, number, number][] {
  // Returns [col, row, distance] for 8-directional neighbors
  // Check bounds, no-fly, diagonal safety
}

function bfsPath(start: [number, number], goal: [number, number], config: GridConfig): [number, number][] {
  // BFS shortest path
}

function bfsDistance(a: [number, number], b: [number, number], config: GridConfig): number {
  // BFS distance between two points
}
```

- [ ] **Step 2: Implement TSP solver**

```typescript
function greedyTsp(dm: number[][]): number[] {
  // Greedy nearest-neighbor TSP
}

function twoOpt(order: number[], dm: number[][]): number[] {
  // 2-opt improvement
}

function solveTsp(dm: number[][], openPath: boolean): number[] {
  // Main TSP solver: greedy + 2-opt
}
```

- [ ] **Step 3: Implement planPath and planPathAll**

```typescript
export function planPath(config: GridConfig): [number, number][] {
  // 1. Collect action cells + start + end
  // 2. Build distance matrix
  // 3. Solve TSP
  // 4. Build full path from order
}

export function planPathAll(config: GridConfig): [number, number][] {
  // Serpentine traversal of all non-no-fly cells
}
```

---

### Task 9: Code Generator (TypeScript)

**Covers:** S6

**Files:**
- Create: `mission-grid-tauri/src/utils/codeGenerator.ts`

**Interfaces:**
- Consumes: `GridConfig`, path from `pathPlanner`
- Produces: `exportMission(config, path): { script: string, shell: string, json: string }`

- [ ] **Step 1: Port code generator**

Port `code_generator.py` to TypeScript. Template literal strings instead of f-strings. Output identical Python/Shell/JSON.

---

### Task 10: Flight Simulation Animation

**Covers:** S3 (animation)

**Files:**
- Create: `mission-grid-tauri/src/components/FlightSimulation.tsx`

**Interfaces:**
- Consumes: path from pathPlanner, grid config
- Produces: Animated drone moving along path with action popups

- [ ] **Step 1: Create FlightSimulation component**

Framer Motion `animate` on drone position, SVG path line with `stroke-dasharray` animation, toast popups on action cells.

---

### Task 11: Rust Backend - File I/O

**Covers:** S7

**Files:**
- Create/Modify: `mission-grid-tauri/src-tauri/src/commands.rs`
- Modify: `mission-grid-tauri/src-tauri/src/main.rs`

**Interfaces:**
- Produces: Tauri commands `save_plan`, `load_plan`, `export_mission`

- [ ] **Step 1: Implement file commands in Rust**

```rust
#[tauri::command]
fn save_plan(path: String, data: String) -> Result<(), String> {
    std::fs::write(&path, data).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_plan(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path).map_err(|e| e.to_string())
}

#[tauri::command]
fn export_mission(dir: String, files: Vec<(String, String)>) -> Result<String, String> {
    // Create dir, write each (filename, content) pair
}
```

- [ ] **Step 2: Register commands in main.rs**

- [ ] **Step 3: Wire save/load/export in frontend via `invoke()`**

---

### Task 12: Rust Backend - MAVLink Telemetry

**Covers:** S7

**Files:**
- Create/Modify: `mission-grid-tauri/src-tauri/src/mavlink.rs`

**Interfaces:**
- Produces: `start_mavlink`, `stop_mavlink`, `send_heartbeat` commands
- Emits: `telemetry-position`, `telemetry-status`, `telemetry-node-status` events

- [ ] **Step 1: Implement UDP listener in Rust**

```rust
use tokio::net::UdpSocket;
use tauri::{AppHandle, Manager};

#[tauri::command]
async fn start_mavlink(app: AppHandle, port: u16) -> Result<(), String> {
    // Spawn tokio task: bind UDP, parse MAVLink, emit events
}
```

- [ ] **Step 2: Wire telemetry events in frontend**

Listen for `telemetry-position` etc. via `listen()` from `@tauri-apps/api/event`.

---

### Task 13: Integration & Polish

**Covers:** S2, S3, S8

**Files:**
- Modify: `mission-grid-tauri/src/App.tsx` (final wiring)

- [ ] **Step 1: Wire all components together in App.tsx**

Full layout: Toolbar top, GridBoard left, SidePanel right, dialogs overlay.

- [ ] **Step 2: Implement save/load with Tauri dialog**

Use `@tauri-apps/api/dialog` for file picker, `invoke` for file I/O.

- [ ] **Step 3: Implement export with directory picker**

- [ ] **Step 4: Implement path planning trigger**

Toolbar "规划路径" button → call `planPath` or `planPathAll` → draw path on grid.

- [ ] **Step 5: Implement simulation trigger**

Toolbar "模拟" button → start FlightSimulation.

- [ ] **Step 6: Visual polish**

Adjust spacing, colors, animations. Ensure Material You consistency.

- [ ] **Step 7: Build and test**

```bash
npm run tauri build
```
Verify the built executable works correctly.
