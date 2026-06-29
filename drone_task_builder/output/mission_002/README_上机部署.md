# mission_002

这个任务包用于网格巡航、动物识别和统计。

## 当前任务流
- 环境启动 (`env_start`)
- 等待定位稳定 (`wait_mapping`)
- 野生动物网格巡航 (`wildlife_grid_patrol`)
- 野生动物识别统计 (`wildlife_detect_animals`)
- 返航 (`return_home`)
- 直接降落 (`land`)

## 上机部署步骤

1. 把整个文件夹复制到机载电脑。
2. 在机载电脑中进入这个目录。
3. 给入口脚本增加执行权限：
   `chmod +x run_wildlife_mission.sh`
4. 运行入口脚本：
   `./run_wildlife_mission.sh`

## 当前入口文件

- `run_wildlife_mission.sh`

## 提示

- 无额外提示。
