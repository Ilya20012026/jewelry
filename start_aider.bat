@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set OPENAI_API_BASE=https://api.zveno.ai/v1
set OPENAI_API_KEY=sk-ph1KQ3RQB6OPMk2v3BdNyPviY-_lm26f5T-G_fye-t4
cd /d "C:\Users\Илья Владимирович\Documents\GitHub\jewelry"
"C:\Users\Илья Владимирович\.local\bin\aider.exe" --model openai/deepseek/deepseek-v3.1-terminus
pause