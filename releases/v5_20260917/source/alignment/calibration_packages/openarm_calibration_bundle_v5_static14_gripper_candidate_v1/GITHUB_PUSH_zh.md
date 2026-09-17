# GitHub 上传说明

当前 `/home/tangyuan/openarm_ws` 的 `.git` 是空目录，不包含 Git 元数据，也没有 remote，因此本环境无法直接提交或推送。

在真实 Git 仓库中执行：

```bash
cd /home/tangyuan/openarm_ws
git status
git add alignment
git commit -m "docs: consolidate OpenArm calibration bundle and gripper protocol"
git push origin HEAD
```

推送前应确认目标 remote、分支和提交内容；本汇总包不会自动创建或猜测 GitHub 仓库地址。
