# 法智问答前端

## 开发运行

```bash
cd frontend
npm install
npm run dev
```

默认访问 `http://127.0.0.1:5173`，Vite 会把 `/api/*` 代理到 `http://127.0.0.1:8000`。

## 生产构建

```bash
npm run build
```

构建文件位于 `frontend/dist`。若前端与后端不在同一地址，请复制 `.env.example` 为 `.env`，设置 `VITE_API_BASE_URL`。

## 已实现功能

- 多轮法律问答与本地历史会话
- RAG/纯对话切换、Top-K 设置
- 引用法条、相关度与低可信度提醒
- 多轮对话步骤和结构化总结
- 独立法条语义检索页
- API 在线状态检测和移动端适配


## API 地址配置

开发环境默认代理到 `http://172.20.10.2:8000`。如地址变化，在 `frontend` 目录新建 `.env`：

```env
VITE_PROXY_TARGET=http://新的IP:8000
```

修改后需重新运行 `npm run dev`。
