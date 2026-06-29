from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ContestPrimitiveTask:
    title: str
    status: str
    detail: str


@dataclass(frozen=True)
class ContestMissionSpec:
    contest_id: str
    name: str
    summary: str
    tasks: List[ContestPrimitiveTask] = field(default_factory=list)


CONTEST_SPECS = [
    ContestMissionSpec(
        contest_id="shelf_inventory",
        name="立体货架盘点无人机系统（D题）",
        summary="重点覆盖货架巡检、二维码识别、货位映射、结果保存和定向查找。",
        tasks=[
            ContestPrimitiveTask("垂直起飞到盘点高度", "已支持", "可用通用起飞任务和货架观察任务组合完成。"),
            ContestPrimitiveTask("按 A/B/C/D 面依次观察货架", "已支持", "可设置每个货架面的观察点、悬停时间和朝向。"),
            ContestPrimitiveTask("识别二维码内容", "已支持", "使用现有二维码识别链路。"),
            ContestPrimitiveTask("把二维码映射到 A1~D6 货位", "已支持", "按画面中的相对位置推断货位编号。"),
            ContestPrimitiveTask("记录盘点结果并导出", "已支持", "自动保存 JSON、CSV 和抓拍图像。"),
            ContestPrimitiveTask("指定货物定向盘点", "已支持", "可设置目标二维码内容，识别到后停止。"),
            ContestPrimitiveTask("激光指示被盘点目标", "部分支持", "可在识别到二维码时短时点亮机载激光。"),
            ContestPrimitiveTask("地面站 LED 联动显示", "暂不支持", "当前应用不生成地面站 LED 控制程序。"),
        ],
    ),
    ContestMissionSpec(
        contest_id="delivery",
        name="送货无人机（B题）",
        summary="重点覆盖坐标送货、颜色形状目标搜索、放货控制和返航降落。",
        tasks=[
            ContestPrimitiveTask("按输入坐标依次送货", "已支持", "可设置多个目标点、巡航高度、下降高度和悬停时间。"),
            ContestPrimitiveTask("控制舵机释放货物", "已支持", "复用现有舵机控制接口。"),
            ContestPrimitiveTask("颜色+形状目标搜索", "已支持", "使用下视图像进行红蓝目标的形状识别与定位。"),
            ContestPrimitiveTask("根据识别结果自动送货", "已支持", "找到目标后自动执行下降、放货和恢复巡航。"),
            ContestPrimitiveTask("送货过程激光标记", "部分支持", "可在悬停投放时点亮机载激光。"),
            ContestPrimitiveTask("语音播报提醒收货", "暂不支持", "当前不生成扬声器播放链路。"),
            ContestPrimitiveTask("红色圆框穿越", "暂不支持", "现有下视相机方案不适合稳定实现立式圆框穿越。"),
        ],
    ),
    ContestMissionSpec(
        contest_id="wildlife",
        name="野生动物巡查系统（H题）",
        summary="重点覆盖禁飞网格配置、网格巡航、动物检测、数量统计和结果保存。",
        tasks=[
            ContestPrimitiveTask("配置禁飞网格", "已支持", "可输入禁飞单元格列表，自动跳过这些区域。"),
            ContestPrimitiveTask("按网格执行覆盖巡航", "已支持", "自动生成蛇形航线并逐格悬停巡检。"),
            ContestPrimitiveTask("识别动物类别", "已支持", "复用现有 animal82.onnx 检测模型。"),
            ContestPrimitiveTask("统计每类动物数量与所在单元格", "已支持", "自动保存单元格记录、标注图和汇总文件。"),
            ContestPrimitiveTask("盘点结果导出", "已支持", "输出 JSON、CSV 和抓拍结果。"),
            ContestPrimitiveTask("激光勾边或轮廓指示", "暂不支持", "当前不生成激光轮廓控制逻辑。"),
            ContestPrimitiveTask("特殊姿态降落到红区", "暂不支持", "当前仅支持常规返航和自动降落。"),
        ],
    ),
]


def format_contest_overview() -> str:
    lines: List[str] = []
    for spec in CONTEST_SPECS:
        lines.append(spec.name)
        lines.append(spec.summary)
        for task in spec.tasks:
            lines.append(f"- {task.title}：{task.status}，{task.detail}")
        lines.append("")
    return "\n".join(lines).strip()
