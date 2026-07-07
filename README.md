# AI错题拆博士---AI中高考错题难题拆解提分博士

一个平台，装下全学段AI 学习工具箱，支持你冲击中高考。本地/线上可运行：真 OCR、PDF/Word 上传、MiniMax/DeepSeek/Fenno 多模型、超细拆题、一题多解、巩固题批改、学习卡片。

## 文档

- [产品介绍](docs/product-intro.md)
- [商业计划书](docs/business-plan.md)
- [部署指南](DEPLOY.md)

## 运行

```powershell
$env:MINIMAX_API_KEY="你的 MiniMax API Key"
python server.py
```

如果系统默认 Python 不可用，可以使用 Codex 自带 Python：

```powershell
$env:MINIMAX_API_KEY="你的 MiniMax API Key"
& "C:\Users\T590\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" server.py
```

打开：

```text
http://127.0.0.1:8020
```

## 部署

部署到服务器请看 [DEPLOY.md](DEPLOY.md)。里面已经配好 Docker Compose、Nginx、systemd、环境变量样例和备份脚本。

## 当前工作流

1. 选择学科或自动识别
2. 上传题目图片
3. MiniMax-M3 视觉 OCR
4. 用户修正题干
5. AI 输出拆解公式、趣味比喻、解题/答题模型
6. AI 输出一题多解/多视角
7. AI 输出小诗/口诀并逐句复盘
8. 生成三道巩固题
9. 学生提交答案后 AI 批改

## 后台配置

在页面左侧进入“后台配置”：

- 可修改或新增模型
- 可切换前台使用模型
- 可修改 OCR、拆题诊断、批改三个提示词
- API Key 保存后只显示掩码
- Fenno 这类 OpenAI 兼容中转可用“Fenno GPT / Fenno GPT-Image2”预设；Fenno 直接填 Base URL `https://api.fenno.ai` 即可，系统会自动调用聊天和图片接口。

## 说明

- 当前暂不做 RAG。
- 当前暂不做正式母题库，但保留 `/api/mother-questions` 接口。
- 数学会输出母题雏形；其他学科会输出题型原型/答题模型雏形。
- MiniMax endpoint 使用当前可连通的 `https://api.minimax.chat/v1/chat/completions`。
