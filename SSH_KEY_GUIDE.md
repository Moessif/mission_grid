# SSH 公钥访问 Gitee 仓库教程

## 为什么用 SSH？
- 不用每次输入用户名密码
- 更安全
- 更方便

---

## 第一步：生成 SSH 密钥

### 打开 Git Bash，输入：
```bash
ssh-keygen -t ed25519 -C "moessif@outlook.com"
```

### 然后一路回车（使用默认设置）：
```
Generating public/private ed25519 key pair.
Enter file in which to save the key (/c/Users/你的用户名/.ssh/id_ed25519): [直接回车]
Enter passphrase (empty for no passphrase): [直接回车]
Enter same passphrase again: [直接回车]
```

### 生成成功后会显示：
```
Your identification has been saved in /c/Users/你的用户名/.ssh/id_ed25519
Your public key has been saved in /c/Users/你的用户名/.ssh/id_ed25519.pub
```

---

## 第二步：复制公钥

### 在 Git Bash 中输入：
```bash
cat ~/.ssh/id_ed25519.pub
```

### 会显示类似这样的内容：
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...你的邮箱
```

### 复制整行内容（从 ssh-ed25519 到邮箱结尾）

---

## 第三步：将公钥添加到 Gitee

### 1. 登录 Gitee
- 打开 https://gitee.com
- 登录你的账号

### 2. 进入 SSH 公钥设置
- 点击右上角头像 → **"设置"**
- 左侧菜单找到 **"SSH公钥"**

### 3. 添加公钥
- **标题**：随便填，比如 "我的电脑"
- **公钥**：粘贴刚才复制的整行内容
- 点击 **"确定"**

---

## 第四步：测试 SSH 连接

### 在 Git Bash 中输入：
```bash
ssh -T git@gitee.com
```

### 如果看到类似这样的提示，输入 `yes`：
```
The authenticity of host 'gitee.com' can't be established.
ECDSA key fingerprint is SHA256:...
Are you sure you want to continue connecting (yes/no)?
```

### 成功后会显示：
```
Hi Moessif! You've successfully authenticated, but GITEE.COM does not provide shell access.
```

---

## 第五步：切换仓库 URL 为 SSH 格式

### 查看当前远程地址：
```bash
git remote -v
```

### 如果显示的是 https 地址，切换为 SSH：
```bash
git remote set-url origin git@gitee.com:moessif/mission_grid.git
```

### 验证修改：
```bash
git remote -v
```
应该显示：
```
origin  git@gitee.com:moessif/mission_grid.git (fetch)
origin  git@gitee.com:moessif/mission_grid.git (push)
```

---

## 完成！现在可以免密操作了

### 测试推送：
```bash
git pull
git push
```

不会再要求输入用户名密码了！

---

## 队友也需要做同样的步骤

让队友也：
1. 生成 SSH 密钥
2. 把公钥添加到他自己的 Gitee 账号
3. 克隆仓库时使用 SSH 地址：
```bash
git clone git@gitee.com:moessif/mission_grid.git
```

---

## 常见问题

### Q: 提示 "Permission denied (publickey)"？
A: 检查：
1. 公钥是否正确添加到 Gitee
2. 是否复制了完整的公钥内容
3. 是否测试过 `ssh -T git@gitee.com`

### Q: 有多台电脑怎么办？
A: 每台电脑都生成自己的密钥，然后都添加到 Gitee 的 SSH 公钥设置里

### Q: 想用原来的 HTTPS 方式？
A: 切换回去：
```bash
git remote set-url origin https://gitee.com/moessif/mission_grid.git
```

---

## SSH 地址格式

Gitee SSH 地址格式：
```
git@gitee.com:用户名/仓库名.git
```

你的仓库：
```
git@gitee.com:moessif/mission_grid.git
```
