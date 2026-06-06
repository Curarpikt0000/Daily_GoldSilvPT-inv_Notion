# Lessons — Daily_GoldSilvPT-inv_Notion

## L-2026-05-30-002: Notion 批量数据清理安全审计与去重防静默失败机制

1. **批量清理脚本默认 Dry Run 保护**：在编写针对 Notion 页面等云端数据的批量清理、删除、归档脚本时，必须遵循安全性第一原则，**默认开启 Dry Run 模式，禁止默认直接写入修改**。应通过显式命令行参数（如 `--execute`）启动实际变更。同时，Dry Run 输出需以对齐排版的表格形式清晰列出待处理页面详情（如 page_id、关键日期、创建时间），便于用户及 Hermes 抽样人工审计。
2. **Notion 查询去重防静默兜底**：在 Notion 数据去重校验中，对关键数据结构（例如 `db_info` 中的 `data_sources`）的存在性应做严格断言。如果预期结构缺失，必须显式抛出异常（如 `RuntimeError`）中断流程，**绝不能以空列表 `[]` 默默兜底**。默默兜底会导致系统误判为“数据不存在”，从而引发持续重复写入。
3. **去重逻辑 Fail Loud 拦截**：去重校验 API 调用一旦发生异常（如超时、限流、权限不足、API 升级不兼容），绝不能仅打印日志并静默 `return`。必须通过 `raise RuntimeError` 将错误抛出（Fail Loud），使得 GitHub Actions 等 CI 任务直接爆红拦截，将错误尽早暴露。

## L-2026-06-06-001: GitHub Actions 定时任务中 GitHub API 请求限流防护

1. **GitHub API 未认证限流风险**：在 GitHub Actions 定时任务中，如果调用 GitHub Repos/Contents API 来拉取存档数据，且没有显式提供认证 Token，请求会以未认证状态执行。由于 GitHub 共享 Runner 的出口 IP 极易在公共池中耗尽未认证限流配额（60次/小时），接口常因 `403 Client Error: rate limit exceeded` 报错崩溃。
2. **Token 降级获取与工作流注入双保险**：
   - **脚本降级读取**：Python 脚本中加载 Token 应增加兜底逻辑：`GITHUB_TOKEN = os.getenv("GH_PERSONAL_TOKEN") or os.getenv("GITHUB_TOKEN")`。
   - **工作流注入**：在 `.github/workflows/` 的运行步骤中，必须显式在 `env` 部分注入 Token，例如 `GH_PERSONAL_TOKEN: ${{ secrets.GITHUB_TOKEN }}`，以确保请求携带有效凭证，从而享受 1000次/小时 的高限流额度。

