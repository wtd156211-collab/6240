# wt-032 causalline 向量时钟与因果排序（从 0 实现）

起始环境只有说明与素材：`samples/` 是事件集与期望结果，`web/` 空着，实现要新写。

## 1. 范围

做的：读入一批带向量时钟的事件（4.1），按第 2 节给出因果判定与全序，按 4.3~4.5 出引擎与页面；测试用标准库
`unittest`（`python -m unittest discover`，覆盖 `samples/`）。

不做：跨批/流式增量；时钟同步与校时修正；多进程/多线程/GPU；网络、数据库、落库；第三方库/CDN/构建；图片；
输入容错（`samples/` 保证合法）；页面编辑事件。

## 2. 口径与公式

时钟 = 「分量名 → 正整数计数」，分量名就是节点名；没写出来的分量等于 0。

- `e ≤ f`：每个分量名 k 上 `e.clock[k] ≤ f.clock[k]`（缺失按 0）；`e < f`：`e ≤ f` 且两时钟不相等。
- 关系三种：`LT`（`e < f`）、`GT`（`f < e`）、`INCOMP`（其余，含两时钟完全相同）。
- 全序即打破规则：排序键 `(时钟字典序, id 字节序)`；时钟字典序 = 两时钟分量名的并集按名字字节序升序逐项比计数
  （缺的一边按 0），第一个不相等的分量定先后；全相等再比 id。它是因果的线性扩展：`e < f` 的事件必排在 f 前面。
- 全序只看事件本身：换个行序写文件，三个输出逐字节相同；`wall` 不参与判定——现场按它排，因果才被排反
  （`samples/notes.md`、`samples/events-skewed.txt`）。

## 3. 数据结构与压缩口径

事件记录 = `id`、`node`、`wall`、`clock`（稀疏、只存非零分量、按名字升序）；关系判定要在与事件总数无关的时间
里出结果。

硬口径：**压缩或裁剪前后每一对事件的判定结果完全相同**，三个子命令输出逐字节一致。允许：只存非零分量、分量
名共享、事件存成「父事件 + 增量」、裁掉对任何一对事件都不产生差别的分量。禁止：给每条事件配与节点数等宽的向量
或位图、只留最近 K 个分量或只留本节点分量、用计数之和或最大值替代逐分量比较。

## 4. 输入输出与文件格式

### 4.1 事件文件（`samples/events-*.txt`）

纯 ASCII、单 `\n` 结尾（无 `\r`/BOM/空行/行尾空格），每行一个事件，四段用单个半角空格分隔：
`<id> <node> <wall> <clock>`。

- `id`、`node`：`[A-Za-z0-9._-]+`、非空，`id` 全批唯一；`wall` 非负整数（毫秒），只作记录。
- `clock`：`名:计数` 用半角逗号连接、段内无空格；名与 `node` 同字符集；计数 `[1-9][0-9]*`（≥ 1、无前导 0）；
  按名字字节序升序、不重复；必须含本事件 `node` 的分量；行序任意。

### 4.2 关系清单（`samples/pairs-*.txt`）

每行两段 `<id_a> <id_b>`，都是事件文件里的 id；行序就是关系输出的行序。

### 4.3 命令行与产物

在仓库根目录执行，退出码 0 表示成功，日志走 stderr；`page` 的显示条数默认 400，实际写
`min(显示条数, 事件总数)` 条：

```
python -m causalline order  <事件> <全序>
python -m causalline relate <事件> <清单> <关系>
python -m causalline page   <事件> <json> [条数]
```

- 全序输出：一行一个 id，第 1 行是全序第 1 位；纯 ASCII、单 `\n`。
- 关系输出：一行 `<id_a> <id_b> <REL>`，与关系清单逐行对应，`REL` 取 `LT`/`GT`/`INCOMP`。

### 4.4 页面数据（`page` 写出的 JSON，键固定）

- `total` 事件总数、`shown` 本次写入条数、`limit` 显示条数。
- `lanes`：`[{"node","first_pos"}]`，只列自己发过事件的节点，按该节点最早事件的全序位置升序，并列按节点名
  字节序。
- `events`：全序前 `shown` 条 `{"id","node","pos","wall","clock"}`，`pos` 从 1 起，`clock` 为
  `[[分量名,计数],…]`（按名字升序）。
- `edges`：可见事件之间的**直接因果对** `{"from","to"}`：`from` 更靠前，可见事件里没有第三个事件 c 使
  `from < c < to`；按 `(from.pos,to.pos)` 升序。
- `stats`：`{"comparable_pairs","incomparable_pairs"}`，数可见事件的两两组合，和 = `shown×(shown-1)/2`。
- `incomparable`：可见事件里不可比较的前 20 对 `[a_id,b_id]`（a 更靠前），按 `(a.pos,b.pos)` 升序。

### 4.5 页面这一侧

- 起服务：仓库根目录 `python -m http.server 8000`，开 `http://127.0.0.1:8000/web/index.html`。页面用原生
  HTML/CSS/ES module，按相对路径 `fetch('data.json')`（`file://` 打不开），不引 CDN、不重算因果。数据：
  `python -m causalline page samples/events-fork.txt web/data.json 400`。
- 必须体现：① 每个节点一条横向泳道，顺序同 `lanes`；② 每个可见事件按 `pos` 从左到右画点并标出 `pos`；③
  `edges` 的因果对连线，方向同全序（`from` → `to`）；④ 不可比较对：两个计数都显示，
  `incomparable` 里的对也列出。
- 数字只来自 JSON：手改 `web/data.json`，刷新就跟着变。

## 5. 性能与验收口径

### 5.1 内存预算

单批事件数可达 `3×10^6`、节点名 `1200` 个、分量总数 `1.2×10^7`；额外峰值 ≤ **512 MiB**，常驻表示 ≤
`48 × 事件数 + 16 × 分量总数 + 8 MiB`，不得有「事件数 × 节点数」量级的结构。量法：`tracemalloc` 包住一次
`order` 取峰值后扣掉该常数。

### 5.2 时间预算

`samples/events-scale.txt`（4 万条、80 节点）上 `order` ≤ **20 秒**、`relate`（`samples/pairs-scale.txt` 的
3000 对）≤ **10 秒**（单进程、含读写、墙钟）；真实规模 `3×10^6` 条事件的 `order` ≤ **60 秒**，单条关系判定必须
与事件总数无关。

### 5.3 验收口径（逐条）

1. 环境：Python 3.13、只用标准库；页面原生 HTML/CSS/ES module，无构建、无 CDN。非法输入、内部结构、日志不查。
2. 正确性：`order`、`relate` 与 `samples/expected-*` 逐字节相同（空格、行序、结尾换行都算）。
3. 确定性：同一输入跑两遍 sha256 一致；打乱事件文件行序重跑，三个输出不变。
4. 压缩不改语义：第 3 节的禁令一条都不能犯；`stale`、`parallel`、`skewed` 专治走捷径的做法。
5. 规模：5.1 的内存、5.2 的时限。
6. 页面：按 4.5 起服务能打开，四项必现信息齐全，数字与 `web/data.json` 一致。
7. 测试：`python -m unittest discover` 跑通，用例只读 `samples/`。

## 6. 样例说明

每个样例四个文件：`events-<case>.txt`、`pairs-<case>.txt`、`expected-<case>.order.txt`、`expected-<case>.rel.txt`。
`case` 后面是事件数、节点数、时钟分量数、查询对数，括号里依次是 LT/GT/INCOMP 的条数：

- `chain`：12、3、30、15（14/1/0）
- `fork`：10、4、25、16（10/1/5）
- `parallel`：6、6、6、15（0/0/15）
- `single`：9、1、9、10（7/3/0）
- `skewed`：10、3、24、12（7/5/0）
- `stale`：10、3、20、15（6/2/7）
- `sparse`：700、2584、2680、30（6/4/20）
- `scale`：40000、80、76560、3000（1079/294/1627）

覆盖点：`chain` 全可比、全序 = 文件序；`fork` 分支互不相关；`parallel` 两两不可比、全序只由打破规则定；`single`
单节点；`skewed` 按 `wall` 升序写、行序与因果被顶反；`stale` 旧分量左右判定，另有两对时钟相等的事件
（`INCOMP`，按 id 破并列）；`sparse` 节点数远大于事件数、每条只有 2-4 分量；`scale` 是 5.2 的时限样例。
`samples/` 合计约 2.2 MiB。

核对（`fork`）：`python -m causalline order samples/events-fork.txt var/o.txt`、
`python -m causalline relate samples/events-fork.txt samples/pairs-fork.txt var/r.txt`，再和
`samples/expected-fork.*.txt` 比，一致即逐字节相同。

## 7. 待补的文档

1. 真实规模的输入与内存口径：`3×10^6` 条事件放不进仓库，要现场自备；`tracemalloc` 峰值从哪一点取，还没定。
2. 其它：客户机器规格、页面配色与横向缩略、`web/data.json` 太大时要不要分片、退出码格式，都没定。
