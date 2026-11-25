# Molish

> **一门用于描述、查询和重放分子与细胞机制的声明式语言。** 用规则描述机制，检查干预如何改变可达状态，并重放经过核查的事件轨迹。
>
> **A declarative language for molecular and cellular mechanisms.** Describe a mechanism as rules, check how an intervention changes what can happen, and replay a verified sequence of events.

[![Specification draft 0.4](https://img.shields.io/badge/Specification-0.4%20draft-4051b5)](engine/Molish-0.4-spec.md)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776ab)](#quick-start)
[![Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue)](LICENSE)

[中文文档](#中文) · [English Documentation](#english) · [语言规范 / Specification](engine/Molish-0.4-spec.md) · [示例轨迹 / Example trace](engine/enzyme-trace.json)

---

## 中文

[快速开始](#快速开始) · [核心特性](#核心特性) · [仓库结构](#仓库结构) · [验证与贡献](#验证与贡献)

### 快速开始

需要 Python 3.9 或更高版本。参考实现只使用 Python 标准库。

```sh
git clone https://github.com/Waylon524/Molish.git
cd Molish
python3 engine/export_enzyme.py enzyme-trace.json
```

示例从 3 个游离底物开始，用实体 ID `101` 跟踪同一个酶。运行一次即可比较正常机制和禁用转化规则后的机制。示例中的计数是离散模型值，每一步表示一次规则应用。

| 情况 | 事件轨迹 | 能否到达产物释放状态 |
| --- | --- | --- |
| 正常 | 游离 → 结合 → 转化 → 释放 | 能。事件见证记录了到达释放的合法步骤，最终有 2 个游离底物和 1 个已释放产物。 |
| 禁用转化 | 游离 → 结合 | 不能。结果保留一条到达结合的见证，以及一份独立的闭包证书，用来核查该初态下无法到达释放。 |

在生成的 JSON 中，`scenarios.normal` 和 `scenarios.blocked` 对应两种情况。`steps` 记录实体 ID、状态、计数、触发规则与证据，`targetReached` 回答释放是否可达，`proof` 保存可供核查的 CBOR 封包。[默认输入](engine/enzyme.json) · [预生成结果](engine/enzyme-trace.json)

要尝试其他初态，把默认输入另存为 `my-enzyme.json`，修改其中的 `entityId`、`region` 或 `initialSubstrate`。这三个字段是酶促示例导出器的配置，通用模型格式见[语言规范](engine/Molish-0.4-spec.md)。

```sh
cp engine/enzyme.json my-enzyme.json
# 编辑 my-enzyme.json，然后重新导出。
python3 engine/export_enzyme.py --source my-enzyme.json my-trace.json
```

### 核心特性

- **机制建模。** 用有稳定 ID 的实体表示分子、复合体和区室，用类型化关系、状态槽和有界计数器表达结合、转运与调节。可复用的规则模板声明参与者类型、守卫和效果。规则与模块的守卫基于同一前态求值，效果作为一次状态变化提交。
- **查询与干预。** 从指定初态搜索目标，可以禁用整条规则或某个具体绑定。事件见证记录可重放的路径。闭包证书列出一组包含初态、在干预下对允许后继封闭且不含目标的状态。
- **版本与来源。** 0.4 草案支持按摘要锁定可复用定义，记录假设、观测和文献等证据，按上下文筛选适用断言，并核查单条轨迹从细粒度模型到粗粒度模型的投影。机器封包采用确定性 CBOR，以 SHA-256 摘要绑定模型、查询和结果。
- **重放与可视化。** 宿主可以通过实体 ID 和区室名把已核查的轨迹绑定到场景。规范定义了面向 Molstage 等宿主的 3D 重放清单和带证据引用的知识图谱快照。TypeScript 空间运行时按宿主提供的区域约束和随机种子，生成可复现的群体位置与插值轨迹。

0.4 仍是规范草案，沿用 0.3 的有限状态执行语义。Python 参考实现面向小型、显式初态模型。物理时间、扩散和反应速率由外部定量模型定义，SBML / BNGL 部分目前只定义适配资格检查。[0.4 语言规范](engine/Molish-0.4-spec.md) · [空间运行时说明](spatial/README.md)

### 仓库结构

| 路径 | 内容 |
| --- | --- |
| [语言规范](engine/Molish-0.4-spec.md) | 0.4 草案、0.3 核心语义和可复现的编码向量 |
| [有限状态核心](engine/finite03.py) | 规则绑定、状态变更和可达性搜索 |
| [0.4 参考实现](engine/molish04.py) | 封包装配、证明核查、轨迹投影与快照 |
| [酶促示例导出器](engine/export_enzyme.py) | 从示例配置构建模型并导出经过核查的轨迹 |
| [空间群体运行时](spatial/README.md) | 独立的 TypeScript 模块与宿主接入示例 |

### 验证与贡献

在仓库根目录运行以下命令，核查 0.3 与 0.4 规范的验收用例、酶促示例的回归测试，以及默认轨迹能否逐字节重建。

```sh
python3 engine/verify03.py
python3 engine/verify04.py
python3 -m unittest discover -s engine
python3 engine/export_enzyme.py | cmp - engine/enzyme-trace.json
```

欢迎报告可复现的模型、编码或验证问题。涉及规则语义时，请附上初态、目标查询、干预条件和预期结果。修改封包或规则语义时，请同步更新规范、编码向量与相关检查。

---

## English

[Quick start](#quick-start) · [Core features](#core-features) · [Repository layout](#repository-layout) · [Verification and contributions](#verification-and-contributions)

### Quick start

Use Python 3.9 or later. The reference implementation uses only the Python standard library.

```sh
git clone https://github.com/Waylon524/Molish.git
cd Molish
python3 engine/export_enzyme.py enzyme-trace.json
```

The example starts with three free substrate molecules and follows the same enzyme, entity `101`. One run compares the mechanism with and without the conversion rule. The counts are discrete model values, and each transition represents one rule application.

| Scenario | Event trace | Is product release reachable? |
| --- | --- | --- |
| Normal | Free → bound → converted → released | Yes. An event witness records a valid path to release, ending with two free substrate molecules and one released product. |
| Conversion disabled | Free → bound | No. The result includes a witness for binding and a separate closure certificate that proves release is unreachable from this initial state. |

In the exported JSON, `scenarios.normal` and `scenarios.blocked` contain the two cases. `steps` records entity IDs, states, counts, rules, and evidence. `targetReached` answers the release query, and `proof` contains the CBOR packages used for verification. [Default input](engine/enzyme.json) · [Pre-generated result](engine/enzyme-trace.json)

To try a different initial condition, copy the default input to `my-enzyme.json` and edit `entityId`, `region`, or `initialSubstrate`. These fields configure the enzyme exporter. For the general model format, see the [language specification (Chinese)](engine/Molish-0.4-spec.md).

```sh
cp engine/enzyme.json my-enzyme.json
# Edit my-enzyme.json, then export the trace.
python3 engine/export_enzyme.py --source my-enzyme.json my-trace.json
```

### Core features

- **Mechanism models.** Give molecules, complexes, and compartments stable IDs. Use typed relations, state slots, and bounded counters to describe binding, transport, and regulation. Reusable rule templates declare typed participants, guards, and effects. Rule and module guards evaluate against the same pre-state, and effects apply as one state transition.
- **Queries and interventions.** Search for a target from a given initial state and disable whole rules or individual bindings. An event witness records a replayable path. A closure certificate identifies a set that contains the initial state, is closed under the allowed transitions, and excludes the target.
- **Versions and provenance.** The 0.4 draft pins reusable definitions by digest, records evidence such as assumptions and observations, filters claims by context, and checks the projection of a single trace from a fine-grained model to a coarser one. Deterministic CBOR provides the machine format, and SHA-256 digests bind models, queries, and results.
- **Replay and visualization.** Host applications can bind checked traces to scenes using entity IDs and compartment names. The specification defines 3D replay manifests for hosts such as Molstage, along with knowledge-graph snapshots that reference evidence. The TypeScript spatial runtime uses host-defined region constraints and a seed to reproduce particle positions and interpolate their motion.

Version 0.4 is a draft built on the 0.3 finite-state semantics. The Python reference implementation targets small models with explicit initial states. Physical time, diffusion, and reaction rates belong to external quantitative models. The SBML and BNGL provisions currently cover eligibility checks for mapping. [0.4 specification (Chinese)](engine/Molish-0.4-spec.md) · [Spatial runtime guide (Chinese)](spatial/README.md)

### Repository layout

| Path | Contents |
| --- | --- |
| [Language specification](engine/Molish-0.4-spec.md) | The 0.4 draft, 0.3 core semantics, and reproducible encoding vectors |
| [Finite-state core](engine/finite03.py) | Rule binding, state updates, and reachability search |
| [0.4 reference implementation](engine/molish04.py) | Package assembly, proof checking, trace projection, and snapshots |
| [Enzyme example exporter](engine/export_enzyme.py) | Builds a model from the example configuration and exports verified traces |
| [Spatial population runtime](spatial/README.md) | Standalone TypeScript module with a host integration example |

### Verification and contributions

Run these commands from the repository root to check the 0.3 and 0.4 conformance cases, run the enzyme regression tests, and reproduce the default trace byte for byte.

```sh
python3 engine/verify03.py
python3 engine/verify04.py
python3 -m unittest discover -s engine
python3 engine/export_enzyme.py | cmp - engine/enzyme-trace.json
```

Reports about models, encodings, or verification are welcome. For a rule semantics issue, include the initial state, target query, intervention, and expected result. Changes to the package format or rule semantics should update the specification, encoding vectors, and relevant checks together.

---

## 许可证 / License

[Apache License 2.0](LICENSE)
