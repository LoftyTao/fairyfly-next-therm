English | [简体中文](README.zh-CN.md)

# Fairyfly-Next THERM

`fairyfly-next-therm` is an exploratory derivative of [fairyfly-therm](https://github.com/ladybug-tools/fairyfly-therm) (modified in 2026) targeting [fairyfly-core](https://github.com/ladybug-tools/fairyfly-core) (`>=0.2.49`) and running [pyHygroThermFEM-Fairyfly](https://github.com/LoftyTao/pyHygroThermFEM-Fairyfly) in an isolated CPython process instead of LBNL THERM 8, with `fairyfly_hygrotherm` automatically registering the `.properties.therm` extension on `fairyfly`. This repository is forward-looking research for Ladybug Tools and easy distribution in Ladybug Tools MCP workflows, and is not planned for long-term maintenance.

Alongside [pyHygroThermFEM-Fairyfly](https://github.com/LoftyTao/pyHygroThermFEM-Fairyfly) and [fairyfly-next-grasshopper](https://github.com/LoftyTao/fairyfly-next-grasshopper), `run_thmz` solves premeshed THMZ files directly using the interpreter configured via `PYHYGROTHERMFEM_FAIRYFLY_PYTHON`, while Rhino native meshing (`QuadRemeshBrep`) runs inside Rhino.

## Install

```powershell
python -I -m pip install "fairyfly-core>=0.2.49" fairyfly-therm-standards==0.1.0
python -I -m pip install -e . --no-deps --config-settings editable_mode=compat
$env:PYHYGROTHERMFEM_FAIRYFLY_PYTHON = "C:\venvs\ff-solver\Scripts\python.exe"
```

This derivative remains licensed under AGPL-3.0, matching upstream `fairyfly-therm`.
