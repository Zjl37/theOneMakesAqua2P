# 太一生水 2P

一款基于大语言模型裁判的双人益智文字游戏

## 规则

![vlcsnap-2024-12-17-00h26m02s116.png](https://s2.loli.net/2024/12/17/nudYlGzkpBQKtSa.png)

![Screenshot 2024-12-16 at 23-02-08 Element Plus Vite Starter.png](https://s2.loli.net/2024/12/17/aDJYPug32fwmNjL.png)

  - 两玩家轮流回答形如“水能产生什么？”的问题，答案须是自然事物，由大模型判定答案正确与否并给出解释。
  - 每个玩家要回答的问题形式中“水”为上一回合玩家给出的事物，如此循环下去。
  - 回答被大语言模型判断为错，或不能在规定时间（20秒）内作答者失败。
  - 当有玩家失败时，游戏立即结束。
  - 「三生万物」，请尝试获得尽可能高的combo！

## 试运行

前端：在子文件夹 `1mkAqua-front` 中运行：

```sh
pnpm install
pnpm dev --host --port 8002
```

后端：在子文件夹 `OneMkAqua-back` 中运行：

```sh
pdm install
pdm run src/onemkaqua_back/server.py
```

网页写死了后端通信端口为3000，请预留出来，并且两个开发服务器启动在同一主机上。

启动后，游戏主页视图的URL为 http://localhost:8002/game

你还需要在创建房间时填入 DashScope API Key 以调用大模型判断你的输入。

## 构建

还没有试过用于部署的构建。后端 `pdm install` 尚会报错。

## 架构

- 前端：Vue 3，Element Plus。是改动不多的 [element-plus-vite-starter 模版](https://github.com/element-plus/element-plus-vite-starter)
- 实时网络通信： Socket.io
- 后端：Python 3，Flask。在游戏进行到特定环节时，通过 Langchain community 框架调用阿里通义大模型API完成用户提交文字的评判。

## ⚠️代码质量警告

此项目为不到两天之内赶制出的［ENGG1015C 大模型应用开发入门］【跨专业发展课程】结课作品，请谨慎阅读代码！

## Credit

Heavily inspired by: https://www.whatbeatsrock.com/
