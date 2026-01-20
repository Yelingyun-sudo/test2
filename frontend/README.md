# Frontend（Next.js）

## 技术栈
- Next.js 15（App Router）+ React 19 RC + TypeScript
- Tailwind CSS + PostCSS/autoprefixer
- shadcn/Radix UI、class-variance-authority、tailwind-merge、tailwindcss-animate
- next-themes、React Hook Form + Zod、sonner、Lucide 等

## 安装与运行
```bash
cd frontend
pnpm install          # 或 npm/yarn
pnpm dev              # 开发
pnpm lint             # 代码检查

pnpm build            # 构建
pnpm start
```

## 环境变量
- 放在 `frontend/.env.local`（示例 `frontend/.env.local.example`）。
- 暴露到浏览器的变量需以 `NEXT_PUBLIC_` 开头，例如：`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api`。

## 目录结构
- `app/`：App Router 页面
- `components/`：UI/Providers
- `lib/`：工具函数
- `public/`：静态资源

## 页面与设计
- 默认首页为登录页（用户名/密码/登录按钮，浅蓝渐变背景，左侧卖点面板）；登录提交为 mock，接入后端后可替换接口。

## 说明
- 使用 Next 官方 ESLint 规则；Tailwind 已配置暗色模式与动画。
- 目前无根 workspace 配置，新增共享包需手动管理。
