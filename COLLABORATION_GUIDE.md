# 地面站软件协作开发方案

## 推荐方案：Git + Gitee/GitHub

### 1. 初始化 Git 仓库

```bash
# 在项目根目录初始化 Git
cd D:\00Ai\Agents\MimoCode\workspace\ticup
git init

# 创建 .gitignore 文件
```

### 2. 建议的仓库结构

```
ticup-ground-station/
├── drone_task_builder/    # 队友开发的任务编排器
├── mission_grid/          # 你开发的网格任务编排器
├── shared/                # 共享代码（可选）
│   ├── common_utils.py    # 通用工具函数
│   └── drone_interface.py # 无人机接口封装
├── docs/                  # 共享文档
├── requirements.txt       # 统一依赖管理
└── README.md              # 项目说明
```

### 3. 分支策略（简化版）

```
main (主分支)
├── dev (开发分支)
│   ├── feature/teammate-task-builder  # 队友的功能分支
│   └── feature/my-mission-grid        # 你的功能分支
└── hotfix/紧急修复
```

### 4. 协作流程

#### 日常开发：
1. 从 `dev` 分支创建功能分支
2. 在功能分支上开发
3. 完成后合并回 `dev` 分支
4. 定期将 `dev` 合并到 `main` 发布

#### 提交规范：
```
feat: 新增功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 重构
test: 测试相关
chore: 构建/工具相关
```

### 5. 具体操作步骤

#### 步骤1：安装 Git
```bash
# Windows 下载安装 Git for Windows
# https://git-scm.com/download/win
```

#### 步骤2：配置 Git
```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

#### 步骤3：初始化仓库并提交
```bash
cd D:\00Ai\Agents\MimoCode\workspace\ticup

# 创建 .gitignore
echo "__pycache__/" > .gitignore
echo "*.pyc" >> .gitignore
echo "dist/" >> .gitignore
echo "build/" >> .gitignore
echo "*.spec" >> .gitignore
echo ".env" >> .gitignore

# 初始化并提交
git init
git add .
git commit -m "feat: 初始化地面站项目"
```

#### 步骤4：创建远程仓库
1. 在 Gitee 或 GitHub 创建新仓库
2. 添加远程仓库：
```bash
git remote add origin https://gitee.com/你的用户名/ticup-ground-station.git
git push -u origin master
```

#### 步骤5：队友克隆并开发
```bash
# 队友克隆仓库
git clone https://gitee.com/你的用户名/ticup-ground-station.git
cd ticup-ground-station

# 创建自己的功能分支
git checkout -b feature/task-builder-improvement

# 开发完成后推送
git add .
git commit -m "feat: 新增任务模板"
git push origin feature/task-builder-improvement

# 创建 Pull Request 或合并请求
```

### 6. 注意事项

#### 避免冲突：
- 各自负责自己的目录（drone_task_builder / mission_grid）
- 修改共享文件前先沟通
- 经常拉取最新代码：`git pull origin dev`

#### 代码同步：
```bash
# 每天开始工作前
git checkout dev
git pull origin dev

# 完成功能后
git checkout dev
git merge feature/你的分支名
git push origin dev
```

### 7. 可选：共享代码抽取

如果两个项目有重复代码，可以考虑抽取到 `shared/` 目录：

```python
# shared/drone_interface.py
class DroneInterface:
    """统一的无人机接口封装"""
    def __init__(self):
        # 复用 uav_ctrl_tools 的接口
        pass
```

### 8. 推荐工具

- **Git GUI**: GitKraken, SourceTree, 或 VS Code 内置 Git
- **代码编辑器**: VS Code + Python 插件
- **协作平台**: Gitee（国内访问快）或 GitHub

## 总结

最简方案：
1. 使用 Git 管理代码
2. 在 Gitee 创建私有仓库
3. 各自负责自己的目录
4. 通过 Pull Request 合并代码
5. 定期同步和沟通

这样既能保证代码安全，又能方便协作开发。