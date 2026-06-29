# utility_marker_demo

这个任务包用于通用小任务组合，比如单点飞行、转向、拍照、目标识别、激光和舵机动作。

## 当前任务流
- ???? (`env_start`)
- ?????? (`wait_mapping`)
- ?? (`takeoff`)
- ???????? (`detect_visual_marker`)
- ???????? (`estimate_visual_marker_coord`)
- ??????? (`land_on_marker`)

## 上机部署步骤

1. 把整个文件夹复制到机载电脑。
2. 在机载电脑中进入这个目录。
3. 给入口脚本增加执行权限：
   `chmod +x run_utility_mission.sh`
4. 运行入口脚本：
   `./run_utility_mission.sh`

## 当前入口文件

- `run_utility_mission.sh`

## 提示

- 通用工具任务包内部会根据动作需要决定是否起飞。
