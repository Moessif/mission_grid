# Git 协作完全新手指南

## 第一步：在 Gitee 上设置仓库权限（让队友能访问）

### 1. 登录 Gitee
- 打开浏览器，访问 https://gitee.com
- 用你的账号登录（moessif）

### 2. 进入仓库设置
- 打开你的仓库：https://gitee.com/moessif/mission_grid
- 点击仓库页面上方的 **"管理"** 选项卡
- 在左侧菜单找到 **"仓库成员管理"**

### 3. 添加队友
- 点击 **"添加仓库成员"** 按钮
- 输入队友的 Gitee 用户名或邮箱
- 权限选择 **"开发者"**（可以推送代码）
- 点击 **"添加"**

### 4. 通知队友
- 告诉队友仓库地址：`https://gitee.com/moessif/mission_grid.git`
- 队友需要先注册 Gitee 账号

---

## 第二步：队友如何克隆仓库（下载代码）

### 队友需要做的：

#### 1. 安装 Git（如果还没安装）
- 下载：https://git-scm.com/download/win
- 安装时全部选默认选项

#### 2. 配置 Git（只需一次）
打开 **Git Bash**（安装后在开始菜单能找到），输入：
```bash
git config --global user.name "队友的名字"
git config --global user.email "队友的邮箱"
```

#### 3. 克隆仓库（下载代码）
```bash
# 打开 Git Bash，进入想存放项目的文件夹
cd ~/Documents

# 克隆仓库
git clone https://gitee.com/moessif/mission_grid.git

# 进入项目目录
cd mission_grid
```

---

## 第三步：日常协作流程（超简单版）

### 每天开始工作前（拉取最新代码）：
```bash
git pull
```

### 修改代码后（提交并推送）：
```bash
# 1. 查看修改了哪些文件
git status

# 2. 添加修改的文件
git add .

# 3. 提交（写清楚改了什么）
git commit -m "描述你做了什么修改"

# 4. 推送到 Gitee
git push
```

### 如果队友也推送了代码（获取更新）：
```bash
git pull
```

---

## 第四步：避免冲突的技巧

### 1. 分工明确
- 你负责 `mission_grid/` 目录
- 队友负责 `drone_task_builder/` 目录
- 各改各的，互不干扰

### 2. 修改前先沟通
- 如果要改共享文件（如 AGENTS.md），先告诉队友
- 改之前先 `git pull` 获取最新版本

### 3. 遇到冲突怎么办？
如果 `git pull` 报错说有冲突：
```bash
# 1. 先看哪些文件有冲突
git status

# 2. 打开有冲突的文件，手动解决
#    文件里会有类似这样的标记：
#    <<<<<<< HEAD
#    你的修改
#    =======
#    队友的修改
#    >>>>>>> abc123

# 3. 删除标记，保留正确的代码

# 4. 添加并提交
git add .
git commit -m "解决冲突"
git push
```

---

## 常用命令速查表

| 命令 | 作用 |
|------|------|
| `git clone <地址>` | 下载仓库 |
| `git pull` | 获取最新代码 |
| `git add .` | 添加所有修改 |
| `git commit -m "说明"` | 提交修改 |
| `git push` | 推送到 Gitee |
| `git status` | 查看状态 |
| `git log` | 查看提交记录 |

---

## 常见问题

### Q: push 时提示要输入用户名密码？
A: 输入你的 Gitee 用户名和密码

### Q: 提示没有权限？
A: 确认队友已经被添加为仓库成员（开发者权限）

### Q: 不小心改错了想撤销？
```bash
# 撤销未提交的修改
git checkout -- 文件名

# 撤销已提交但未推送的修改
git reset --soft HEAD~1
```

### Q: 想看看改了什么？
```bash
# 查看具体修改内容
git diff
```

---

## 团队协作建议

1. **每天开始前**：`git pull` 获取最新代码
2. **完成一个小功能就提交**：不要攒一大堆再提交
3. **提交信息要清楚**：写明白做了什么，比如 "fix: 修复网格显示bug"
4. **有冲突先沟通**：不要强行覆盖队友的代码
5. **重要修改前先备份**：复制一份项目文件夹以防万一

---

## 你的仓库信息

- **仓库地址**：https://gitee.com/moessif/mission_grid.git
- **你的用户名**：Moessif
- **你的邮箱**：moessif@outlook.com

队友克隆命令：
```bash
git clone https://gitee.com/moessif/mission_grid.git
```
