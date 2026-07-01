"""
MissionGrid 地面站启动脚本
==========================

这是应用的最顶层入口文件。

使用方式：
    python app.py

启动流程：
    app.py → mission_grid_app.main.run() → QApplication → MainWindow
"""

from mission_grid_app.main import run

if __name__ == "__main__":
    run()
