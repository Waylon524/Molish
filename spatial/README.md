# 空间群体运行时

`spatial-population.ts` 根据粒子数量、合法区域和种子生成初始位置与固定步长的轨迹。宿主应用提供区域检查，并把返回的位置用于绘制。逻辑模型的规则、计数和证书由 Molish 执行器处理。

| 配置字段 | 含义 |
| --- | --- |
| `kind` | 配置格式 `molish-spatial-population/1` |
| `id` | 群体标识。群体内的对象使用从 0 起的序号 |
| `region` | 匹配宿主区域的 `id` |
| `count` | 对象数量，0–4096 的整数 |
| `radius` | 球形包络的半径，单位由宿主场景决定 |
| `maxStep` | 单次更新的最大位移，单位与半径一致 |
| `seed` | 32 位无符号随机种子 |

## 定义区域

`minimum` 和 `maximum` 给出采样用的包围盒。宿主实现的 `fits(point, radius)` 判断整颗球是否位于区域内。可选的 `fitsSegment(from, to, radius)` 检查球沿实际线段移动时扫过的空间。对于有内壁或孔洞的区域，两端合法仍可能穿墙，宿主需要检查整条路径。缺少 `fitsSegment` 时，运行时用扩大起点包络球的方式保守检查。

下面用一个轴对齐盒子定义区域。对固定半径的球，允许其球心进入的区域仍是凸盒，因此检查线段两端就足够。在 Node.js 22.18+ 可将代码保存为 `spatial/box-example.ts` 后执行 `node spatial/box-example.ts`。

```typescript
import { createSpatialPopulation, type PopulationRegion } from './spatial-population.ts';

const box: PopulationRegion = {
  id: 'box',
  minimum: [0, 0, 0],
  maximum: [1, 1, 1],
  fits(point, radius) {
    return point.every(value => value >= radius && value <= 1 - radius);
  },
  fitsSegment(from, to, radius) {
    return this.fits(from, radius) && this.fits(to, radius);
  },
};

const enzymes = createSpatialPopulation({
  kind: 'molish-spatial-population/1',
  id: 'soluble-enzymes',
  region: 'box',
  count: 30,
  radius: 0.01,
  maxStep: 0.015,
  seed: 597321,
}, box);

enzymes.step();
console.log(enzymes.sample(0, 0.5));
```

`step()` 前进一步。宿主可用 `POPULATION_STEP_SECONDS` 累计播放时间，每经过 1/30 秒调用一次。`sample(index, fraction)` 在前一状态与当前状态之间插值，`fraction` 范围为 0–1。`reset()` 用原种子重新生成初态。

需要复现轨迹时，记录群体配置、区域版本和 `POPULATION_MOTION_VERSION`。空间步长用于呈现，单位和时间比例由应用定义。当前运行时允许个体相互重叠，适用于背景群体和教学运动。

[返回 Molish README](../README.md)
