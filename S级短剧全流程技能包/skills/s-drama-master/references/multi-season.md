# 多季短剧架构与续写协议

本协议把“一部剧”与“一季剧”分开管理。用户可以在启动时输入季数，也可以先完成第一季，再按季续写。每一季都必须单独通过时长、因果、人物和交付检查；系列总时长可以超过 140 分钟，但任一季不得超过 140 分钟（8400 秒）。

## 一、启动参数

`project.json` 至少保留以下字段。没有用户指定时使用一季、每季 120 集的默认值；用户明确输入的季数和每季集数覆盖默认值。

```json
{
  "series_id": "SERIES-001",
  "season_count": 1,
  "season_input_mode": "manual",
  "active_season": "S01",
  "total_episodes": 120,
  "season_defaults": {
    "episode_count": 120,
    "runtime_budget": {
      "max_total_seconds": 8400,
      "opening_min_seconds": 120,
      "opening_max_seconds": 180,
      "later_min_seconds": 60,
      "later_max_seconds": 90
    }
  },
  "seasons": [
    {
      "season_id": "S01",
      "season_number": 1,
      "title": "",
      "episode_count": 120,
      "status": "planned",
      "runtime_budget": {
        "max_total_seconds": 8400,
        "opening_target_seconds": 150,
        "later_target_seconds": 65
      },
      "season_promise": "本季要解决的主矛盾",
      "carry_in": [],
      "carry_out": []
    }
  ],
  "series_canon_version": 1,
  "cross_season_mode": "locked-canon-with-handoff"
}
```

`season_count` 是计划季数，不代表已经写完；`status` 只能在对应正文和审稿完成后改为 `delivered`。如果用户只说“以后还要续季”但未给季数，保持 `season_count: 1`，把续季可能性记入 `cross_season_mode` 和 `open_series_threads`，不要擅自生成空白季的正文。

每季可以独立设置 `episode_count`、前三集时长和后续单集时长，但 `runtime_budget.max_total_seconds` 不得大于 8400。默认分配仍为前三集 120—180 秒、其余 60—90 秒；写作前生成该季完整的 `episode_runtime_seconds`，计算式为：

```text
sum(Sxx.episode_runtime_seconds) <= Sxx.runtime_budget.max_total_seconds
```

超出上限时优先压缩重复解释和无后果场面，不能静默删掉结局、伏笔回收或关系结果。系列累计时长只做信息统计，不把各季相加后再错误套用 140 分钟上限。

## 二、文件分层

单季项目可以继续使用现有根目录结构。`season_count > 1` 时，每季放在独立目录，系列级事实放在顶层：

```text
project.json
progress.json
series/
  series-canon.md                 # 跨季不变事实、系列主题和终点
  series-story-graph.json         # 跨季因果边和伏笔图
  season-index.md                 # 各季状态、时长、交接版本
  open-series-threads.md          # 尚未回收且允许跨季的线
canon/
  name-ledger.md                  # 全系列姓名和称呼唯一台账
  cross-season-ledger.csv         # 跨季资源、秘密、关系与资产变化
  season-handoffs/
    S01-to-S02.md                 # 上季封存状态与下季启动包
seasons/
  S01/
    01-positioning.md
    02-characters.md              # 只新增或修订，不复制全系列事实
    03-structure.md
    03-causality-map.md
    04-episodes.md
    04-runtime-budget.md
    05-opening-three.md
    episodes/S01-EP001.md ...
    canon/knowledge.md
    canon/promises.md
    production/...
    review/...
    deliverables/...
  S02/
    ...
```

现有 `episodes/EP001.md` 等扁平路径仍可作为 S01 的兼容写法；一旦出现第二季，后续正文必须写入带季号的路径，不能让 `EP001` 在不同季互相覆盖。导出时同时保存 `season_id`、本季编号和全局编号。

## 三、编号与跨季边

- 人物、地点、规则和道具本体 ID 在系列内稳定：`C01`、`L01`、`R01`、`P01`。
- 资产剧情变体带季号，避免同名覆盖：`S01-C01-V03`、`S02-C01-V01`；若完全复用上季版本，直接引用原 ID，并记录 `reuse_from: S01-C01-V03`。
- 集、场、节拍保留本季本地编号，同时生成全局 ID：`S01-EP001`、`S01-EP001-S01`、`S01-EP001-B01`。旧项目只出现 `EP001` 时视为 S01 的本地编号。
- 主线和支线允许跨季：`M01`、`B02` 不因换季重编号；新增本季线使用 `S02-M03` 或在现有线路下添加阶段节点。
- 跨季事件边写入 `series-story-graph.json`，`kind` 可取 `season_bridge`（上季结果改变下季条件）、`carryover`（资源/关系/信息携带）、`reveal`、`consequence`。每条边都要有 `from_season`、`to_season`、`reason` 和正文或交接证据。

## 四、季末封存与季间交接

一季交付前用[季间交接模板](../assets/season-handoff-template.md)生成 `canon/season-handoffs/S01-to-S02.md`。它不是新的剧情大纲，而是下季可以安全续写的事实快照，至少包含：

```text
上季：S01     封存 canon 版本：v__
本季已解决的主承诺：PR__、PR__
仍开放的系列承诺：PR__（计划兑现季/条件）
季末主矛盾结果：谁做了什么选择，得到什么结果，承担什么代价
人物位置：C__ 的目标、关系、伤病、秘密、知情范围、下一步压力
世界规则变化：新增/废止/被证明错误的 R__
资源账：金钱、机会、次数、证据、声誉、关键物件的余额和持有人
时间线：故事时间、季末到下季开场的间隔、不可跳过的事件
资产状态：人物妆发/服装/发饰、场景损坏或修复、道具完整性及持有人
未回收伏笔：F__ 的首现、强化、误读、计划回收和失败代价
下一季入口条件：必须先成立的事实、可使用的旧资产版本
禁止漂移：不可改写的姓名、关系结果、规则边界和已发生事实
下季可变空间：新目标、新地点、新对手和新卖点的设计范围
```

季末必须先给本季主矛盾一个结果和余波，再放下季钩子。仅以“真正的阴谋才刚开始”结束而没有本季结果，标记为 `open-cliffhanger-risk`，审稿不通过，除非用户明确要求纯悬置结尾。

## 五、续写下一季的执行顺序

收到“继续第 N 季”“写下一季”或用户输入季号时：

1. 读取 `series-canon.md`、上一季交接文件、`cross-season-ledger.csv`、全局故事图和上一季最终审稿问题。
2. 校验上一季是 `delivered` 或用户明确允许带问题续写；若存在未解决的关键连续性问题，先列出影响，不把问题悄悄变成新季事实。
3. 创建/读取 `seasons/SNN/`，登记本季规格和不超过 8400 秒的独立预算。不得复制上一季的 `EP001` 文件作为新稿。
4. 先写本季定位增量、人物关系变化、主线阶段和季内因果图；本季可以换主卖点，但必须说明它如何承接上季代价与悬念。
5. 为前三集重新设计本季开局。可以用新钩子、误会、系统限制或新场景，但不能重新解释观众已经知道的系列背景；只在当前行动需要时补充后置信息。
6. 按本季批次写正文；每批同时更新本季 canon、全局图、资产变体和 `cross-season-ledger.csv`。上季资产只有在状态和时间线允许时复用。
7. 季末完成本季结局、交接文件、时长检查和审稿，再把 `season_index` 的状态改为 `delivered`。

续写提示可以使用：

```text
继续系列《项目名》的第 S02 季。
读取：series/series-canon.md、canon/season-handoffs/S01-to-S02.md、
canon/cross-season-ledger.csv、series/series-story-graph.json、
seasons/S02/project.json（若存在）。
本季集数：__；每季总时长硬上限：8400 秒；前三集 120—180 秒，其余 60—90 秒。
先输出本季承接核对和增量定位，再按总控完成分集与正文；不重置姓名、关系、规则、道具持有人或资产历史。
```

## 六、跨季连续性检查

每批和季末至少检查：

1. 上季选择是否留下真实资源、关系或声誉代价，而不是新季开头自动清零。
2. 下季人物的知识边界是否从上季交接逐项继承；不知道的秘密不能因换季自动变成已知。
3. 姓名、称呼、年龄、伤痕、妆容、发饰、道具持有人、场景损坏状态和故事时间是否有交接依据。
4. 跨季伏笔是否标明“本季回收”“系列回收”或“放弃并解释”，不能把计划节点冒充已兑现。
5. 新季重复使用的爽点、误会或能力是否带来新的策略、限制或后果；只换地点和反派名字不算新季推进。
6. 每季总秒数独立核算；当前季通过不代表全系列完成，系列交付仍需逐季列出状态。

输出 `evidence` 时增加 `season_id` 与 `cross_season_evidence`；输出 `canon_delta` 时说明变更属于本季还是系列级事实。任何系列级变更都要回溯受影响季和交接文件。
