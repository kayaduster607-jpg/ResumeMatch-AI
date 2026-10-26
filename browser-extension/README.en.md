# Job Import Browser Extension

[简体中文](README.md) | [English](README.en.md)

Search recruitment platforms in a signed-in browser, retrieve full JDs, and send them to ResumeMatch-AI. This extension handles **job import**, not resume parsing or match scoring. Continue analysis in the main application after import.

## Connect to the correct backend first

Follow the [main README](../README.en.md) to start backend 9000 and frontend 5173. The extension source currently defaults to 8000. Align three places before loading:

1. Change the API address in popup “设置” (settings) to `http://localhost:9000`.
2. Change DEFAULT_API in `popup.js` to the same address.
3. **Append** `http://localhost:9000/*` to the existing host_permissions array in `manifest.json`, retaining recruitment-platform permissions.

Reload the extension in its management page. Changing settings alone can still fail if permissions remain on 8000. Check service interfaces at `http://localhost:9000/docs`.

## Install and import a role

1. Open `edge://extensions/` in Edge or `chrome://extensions/` in Chrome and enable developer mode.
2. Choose the unpacked-extension loader and select this README's `browser-extension` directory, not an individual file.
3. Sign into the target recruitment platform in the same browser profile. Platforms have independent login states.
4. Open the extension, choose a platform, enter a keyword such as “Python 后端实习生”, select city / experience / education, and click “搜索” (search).
5. Open an original job page to check its contents, then click “获取详情并导入” (fetch details and import). For batches, use “全部导入系统” (import all).
6. After the green imported mark appears, check the JD text at `/jd` in the main application. Then upload a PDF resume, select that JD, and analyze.

For long searches or batch imports, use “标签页” (tab) in the popup's lower-right corner so loss of focus does not close the popup.

## Inputs and results

| Input | Result | Verification |
| --- | --- | --- |
| Platform, keyword, filters | Job list | Check the original platform page |
| Selected role | Full JD and import result | Main application contains a complete JD record |
| Resume and JD in main application | Subsequent match report | View the main report, separately from extension search results |

Adapters cover BOSS, Zhaopin, Liepin, and 51job, with basic support for 51job. Platform APIs and access conditions may change. If collection fails, paste the JD manually in the main application to retain the full matching workflow.

## Troubleshooting and changes

| Symptom | Check |
| --- | --- |
| Login required | Sign into that platform in the profile containing the extension |
| No search results | Platform, keyword, city, and current access conditions |
| Results appear but import fails | Backend running; settings, DEFAULT_API, and host_permissions all use 9000 |
| Script updates do not appear | Reload the extension and refresh the platform page if needed |

`manifest.json` declares permissions, `popup.js` organizes search and import, and `content.js` runs platform adapters. The manifest defines the version. Report platform, reproduction steps, and sanitized errors, without account sessions or real resumes.
