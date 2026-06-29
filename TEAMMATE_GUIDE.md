# 队友加入协作指南

## 你需要做的全部步骤

---

### 第一步：注册 Gitee 账号

1. 打开 https://gitee.com
2. 点击右上角 **"注册"**
3. 填写邮箱、用户名、密码
4. 完成邮箱验证

---

### 第二步：安装 Git

1. 下载：https://git-scm.com/download/win
2. 安装时全部选默认选项
3. 安装完成后，开始菜单会出现 **"Git Bash"**

---

### 第三步：生成 SSH 密钥

1. 打开 **Git Bash**
2. 输入以下命令（把邮箱改成你的）：
```bash
ssh-keygen -t ed25519 -C "你的邮箱@example.com"
```
3. 一路回车（不设密码）
4. 复制公钥：
```bash
cat ~/.ssh/id_ed25519.pub
```
5. 复制显示的整行内容（从 `ssh-ed25519` 开始）

---

### 第四步：把公钥添加到 Gitee

1. 登录 Gitee
2. 点击右上角头像 → **"设置"**
3. 左侧菜单 → **"SSH公钥"**
4. 标题随便填（比如"我的电脑"）
5. 公钥粘贴刚才复制的内容
6. 点击 **"确定"**

---

### 第五步：告诉仓库管理员你的 Gitee 用户名

把你的 Gitee 用户名发给仓库管理员，让他把你添加为仓库成员。

---

### 第六步：克隆仓库

等管理员添加你后，在 Git Bash 中执行：

```bash
# 进入你想存放项目的文件夹
cd ~/Documents

# 克隆仓库
git clone git@gitee.com:moessif/mission_grid.git

# 进入项目目录
cd mission_grid
```

---

### 第七步：配置 Git 用户信息

```bash
git config user.name "你的名字"
git config user.email "你的邮箱@example.com"
```

---

## 完成！现在可以开始协作了

### 日常工作流程：

**开始工作前（获取最新代码）：**
```bash
git pull
```

**修改代码后（提交并推送）：**
```bash
git add .
git commit -m "描述你做了什么"
git push
```

---

## 你的分工

根据项目结构，你主要负责：
- `drone_task_builder/` 目录（任务编排器）

另一个队友负责：
- `mission_grid/` 目录（网格任务编排器）

**注意**：不要修改对方负责的目录，避免冲突。

---

## 常见问题

### Q: 克隆时提示 "Permission denied"？
A: 检查：
1. 是否已添加 SSH 公钥到 Gitee
2. 是否已告诉管理员你的用户名
3. 管理员是否已把你添加为仓库成员

### Q: push 时提示没有权限？
A: 联系管理员，确认你的权限是 "开发者"（可以推送代码）

### Q: 不小心改了对方的文件怎么办？
```bash
# 撤销修改
git checkout -- 文件名
```

---

## 需要帮助？

遇到问题可以问仓库管理员，或者查看：
- Git 基础教程：https://git-scm.com/book/zh/v2
- Gitee 帮助文档：https://gitee.com/help
