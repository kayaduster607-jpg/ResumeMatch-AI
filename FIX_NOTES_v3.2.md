# ResumeMatch-AI v3.2 修复说明

本版针对用户截图和当前运行问题做了以下修复：

1. BOSS / Edge 抓取
   - 修复重复启动同一个 Edge 用户目录导致 `BrowserContext.new_page: Target page, context or browser has been closed` 的问题。
   - 已运行的项目专用 Edge 会通过 DevTools `/json/new` 打开新标签，不再二次拉起冲突进程。
   - BOSS 页面已显示岗位卡片时，增强 DOM 采集选择器，支持 `.job-card-wrap`、动态 class、岗位链接兜底和文本启发式解析。
   - “采集当前 Edge 页面”会跳过已关闭标签页，避免一个关闭页导致整次采集失败。

2. 城市过滤
   - 保留城市硬过滤，不再做区域/区县过滤。
   - 不再把外地县镇、区县强行改成目标城市。

3. 分析页数据清理
   - 简历候选区支持删除简历。
   - 岗位候选区支持删除岗位。
   - 历史分析记录支持单条删除。
   - 删除简历/岗位时会联动删除关联分析、改写和面试记录。

4. 简历导出模板
   - Word/PDF 导出不再是纯文本。
   - 新增 A4 简历版式：顶部姓名与求职意向信息栏、蓝色章节标题、项目/技能 bullet 样式、段落前缀加粗。
   - 改写页预览也改成接近导出版式的简历纸张效果。

5. 验证
   - Python: `python3 -m compileall backend/app`
   - Frontend: `npm run build`
