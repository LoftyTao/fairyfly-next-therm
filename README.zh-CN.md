[English](README.md) | 简体中文

# Fairyfly-Next THERM

`fairyfly-next-therm` 是基于 [fairyfly-therm](https://github.com/ladybug-tools/fairyfly-therm) 修改的前瞻研究衍生库（修改于 2026 年），对接上游 [fairyfly-core](https://github.com/ladybug-tools/fairyfly-core)（`>=0.2.49`），并通过隔离的 CPython 子进程调用 [pyHygroThermFEM-Fairyfly](https://github.com/LoftyTao/pyHygroThermFEM-Fairyfly) 替代 LBNL THERM 8，由 `fairyfly_hygrotherm` 自动向 `fairyfly` 注册 `.properties.therm` 扩展属性。本项目面向 Ladybug Tools 与 Ladybug Tools MCP 易分发方案的探索研究，无长期维护计划。

本库配合 [pyHygroThermFEM-Fairyfly](https://github.com/LoftyTao/pyHygroThermFEM-Fairyfly) 与 [fairyfly-next-grasshopper](https://github.com/LoftyTao/fairyfly-next-grasshopper) 使用，其中 `run_thmz` 可经由 `PYHYGROTHERMFEM_FAIRYFLY_PYTHON` 指定的独立解释器直接求解预分网 THMZ 文件，而调用 Rhino 原生网格划分（`QuadRemeshBrep`）的操作需在 Rhino 内运行。

## 安装

```powershell
python -I -m pip install "fairyfly-core>=0.2.49" fairyfly-therm-standards==0.1.0
python -I -m pip install -e . --no-deps --config-settings editable_mode=compat
$env:PYHYGROTHERMFEM_FAIRYFLY_PYTHON = "C:\venvs\ff-solver\Scripts\python.exe"
```

本衍生库沿用上游 `fairyfly-therm` 的 AGPL-3.0 开源协议。
