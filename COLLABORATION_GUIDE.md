# MissionGrid 协作开发指南

## 项目概述

MissionGrid 是基于 PySide6 的无人机网格任务编排地面站，运行在 Windows 上，用于编排 OrangePi CM5 机载电脑的飞行任务。

## 分支策略

```
master (稳定版本)
├── dev/mori (mori 的开发分支)
└── dev/xxx (其他人的开发分支)
```

**规则**：
- `master`: 随时可运行的稳定版本
- `dev/mori`: 你的开发分支，自由提交
- 完成功能后：提 PR 合并到 master

## 快速开始

### 1. 环境准备

#### 安装 Git
1. 下载：https://git-scm.com/download/win
2. 安装时全部选默认选项
3. 安装完成后，开始菜单会出现 **"Git Bash"**

#### 配置 Git
```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

#### 设置 SSH 密钥（推荐）

SSH 密钥可以免去每次输入用户名密码的麻烦：

```bash
# 1. 生成密钥（在 Git Bash 中执行）
ssh-keygen -t ed25519 -C "你的邮箱@example.com"
# 一路回车使用默认设置

# 2. 查看公钥
cat ~/.ssh/id_ed25519.pub

# 3. 复制公钥内容，添加到 GitHub：
#    - 打开 https://github.com/settings/keys
#    - 点击 "New SSH key"
#    - 粘贴公钥内容
#    - 点击 "Add SSH key"

# 4. 测试连接
ssh -T git@github.com
```

### 2. 克隆仓库

```bash
# 使用 SSH（推荐）
git clone git@github.com:Moessif/mission_grid.git

# 或使用 HTTPS
git clone https://github.com/Moessif/mission_grid.git

cd mission_grid
```

### 2. 切换到你的分支

```bash
git fetch origin
git checkout dev/mori
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行程序

```bash
python app.py
```

## 日常开发流程

### 每天开始工作前

```bash
# 1. 拉取最新代码
git checkout dev/mori
git pull origin dev/mori

# 2. 合并 master 的最新改动（如果有）
git merge master
```

### 开发过程中

```bash
# 1. 写代码...

# 2. 定期提交（小步提交，避免大改动）
git add .
git commit -m "feat: 新增xxx功能"

# 3. 推送到远程
git push origin dev/mori
```

### 完成功能后

```bash
# 1. 确保代码能运行
python app.py

# 2. 推送最终代码
git push origin dev/mori

# 3. 在 GitHub 上创建 Pull Request
#    - 源分支: dev/mori
#    - 目标分支: master
#    - 描述你做了什么
```

## 代码规范

### 文件组织

```
mission_grid/
├── app.py                 # 入口（不要修改）
├── mission_grid_app/      # 主要代码目录
│   ├── main_window.py     # 主窗口（谨慎修改）
│   ├── models.py          # 数据模型
│   ├── your_new_file.py   # 你的新文件
│   └── ...
├── config.json            # 配置文件（不要提交）
└── log/                   # 日志（不要提交）
```

### 提交信息规范

```
feat: 新增xxx功能
fix: 修复xxx问题
docs: 更新文档
style: 代码格式调整
refactor: 重构xxx
test: 添加测试
chore: 构建/工具相关
```

**示例**：
```bash
git commit -m "feat: 新增任务模板选择功能"
git commit -m "fix: 修复路径规划时的越界错误"
git commit -m "docs: 更新 README 使用说明"
```

## 避免冲突的策略

### 1. 分工明确

| 负责人 | 负责模块 | 文件 |
|--------|----------|------|
| 你 | 主窗口、标签页 | main_window.py |
| mori | 新功能模块 | your_new_module.py |
| 共享 | 数据模型 | models.py（修改前沟通） |

### 2. 修改共享文件前

```bash
# 1. 先拉取最新
git pull origin dev/mori

# 2. 检查文件是否被修改
git log --oneline -5 mission_grid_app/models.py

# 3. 如果最近有改动，先沟通
```

### 3. 处理冲突

如果发生冲突：

```bash
# 1. 拉取最新
git pull origin dev/mori

# 2. 如果提示冲突，手动解决
# 打开冲突文件，找到 <<<<<<< HEAD 和 >>>>>>> 标记
# 选择保留哪个版本，删除标记

# 3. 标记冲突已解决
git add .
git commit -m "merge: 解决合并冲突"
```

## 代码合并流程

### 方案 A：直接合并（简单）

```bash
# mori 完成功能后
git checkout master
git merge dev/mori
git push origin master
```

### 方案 B：Pull Request（推荐）

1. 在 GitHub 上创建 PR
2. 代码审查（可选）
3. 合并 PR
4. 删除已合并的分支

```bash
# 合并后清理
git branch -d dev/mori
git push origin --delete dev/mori
```

## 沟通机制

### 需要沟通的情况

- 修改 `models.py`（数据结构）
- 修改 `main_window.py`（主窗口）
- 添加新的依赖包
- 改变文件组织结构
- 遇到问题或疑问

### 沟通方式

- **日常**: 微信/QQ 群
- **代码审查**: GitHub PR 评论
- **文档**: 直接修改 README.md

## 常见问题

### Q: 我的分支落后了怎么办？

```bash
git checkout dev/mori
git merge master
# 如果有冲突，解决后提交
```

### Q: 不小心提交到 master 了？

```bash
# 撤销最后一次提交（保留改动）
git reset --soft HEAD~1

# 改到自己的分支
git checkout -b dev/mori
git commit -m "feat: xxx"
```

### Q: 想放弃本地改动？

```bash
# 放弃所有未提交的改动
git checkout -- .

# 放弃特定文件
git checkout -- path/to/file.py
```

### Q: 如何查看谁改了什么？

```bash
# 查看文件修改历史
git log --oneline mission_grid_app/models.py

# 查看某次提交的改动
git show <commit-hash>

# 查看当前改动
git diff
```

## 推荐工具

- **Git GUI**: VS Code 内置 Git、GitKraken、SourceTree
- **代码编辑器**: VS Code + Python 插件
- **终端**: Windows Terminal 或 PowerShell

## 检查清单

提交前确认：

- [ ] 代码能正常运行 (`python app.py`)
- [ ] 没有语法错误
- [ ] 提交信息清晰
- [ ] 没有提交临时文件 (config.json, log/, __pycache__/)
- [ ] 如果修改了共享文件，已沟通

## 紧急情况

### 代码搞坏了

```bash
# 回退到上一次提交
git reset --hard HEAD~1

# 回退到特定版本
git reset --hard <commit-hash>
```

### 远程仓库有问题

```bash
# 强制同步远程（谨慎使用）
git fetch origin
git reset --hard origin/master
```

## 总结

1. **在自己的分支上开发** (`dev/mori`)
2. **小步提交**，频繁推送
3. **修改共享文件前沟通**
4. **完成功能后提 PR**
5. **保持代码能运行**

祝开发顺利！
