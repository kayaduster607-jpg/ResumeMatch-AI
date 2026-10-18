#!/usr/bin/env bash
set -euo pipefail
export PYTHONUTF8=1

echo "ResumeMatch-AI 岗位爬虫交互启动器"
python -m job_crawler
