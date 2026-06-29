# delivery_coordinates_demo

这个任务包用于坐标送货或颜色形状目标搜索后送货。

## 当前任务流
- 环境启动 (`env_start`)
- 等待定位稳定 (`wait_mapping`)
- 按坐标送货 (`delivery_coordinates`)
- 送货释放货物 (`delivery_release_cargo`)
- 返航 (`return_home`)
- 直接降落 (`land`)

## 上机部署步骤

1. 把整个文件夹复制到机载电脑。
2. 在机载电脑中进入这个目录。
3. 给入口脚本增加执行权限：
   `chmod +x run_delivery_mission.sh`
4. 运行入口脚本：
   `./run_delivery_mission.sh`

## 当前入口文件

- `run_delivery_mission.sh`

## 说明

- 这个导出包不会修改你原来的 `competition_pkg` 旧脚本。
- 当前版本优先复用你已经验证过的参考脚本和现有机载控制接口。
- 如果你后面要扩展更多基础任务，建议继续在这个导出器上增加任务映射，而不是直接改旧脚本。

## 提示

- 导出包会自动生成启动脚本，“环境启动”任务主要用于方案表达。
