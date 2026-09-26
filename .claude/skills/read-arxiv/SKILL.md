---
name: read-arxiv
description: 精读 arXiv 论文，生成 6 节结构化中文报告。当用户要读论文、精读 arxiv 文章、分析论文时触发。用户可调用 /read-arxiv 来激活。
user-invocable: true
allowed-tools: "Bash, Read, Write, Edit"
---

# Read Arxiv — 精读 arXiv 论文

对 arXiv 论文深度精读，生成 6 节结构化中文报告。**Claude 自身作为分析引擎**，无需外部 LLM API。

## 输入

用户提供 arXiv ID（`2310.01234`）或完整 URL（`https://arxiv.org/abs/2310.01234`）。

## 执行流程

### Step 1：解析 arXiv ID 和确定输出目录

```bash
# 从用户输入中提取纯 ID（去掉 URL 前缀、空格、尾部斜杠）
# 如 "https://arxiv.org/abs/2310.01234" → "2310.01234"
```

设 `ID` 为提取后的纯 arxiv ID，输出路径为 `outputs/<ID>/report.md`。

若该文件已存在，询问用户是否加 `--force` 覆盖，否则直接退出。

### Step 2：下载 PDF

使用国内镜像下载（速度从几 KB/s → 秒级）：

```bash
wget -O "outputs/<ID>/<ID>.pdf" "https://cn.arxiv.org/pdf/<ID>"
```

需要先 `mkdir -p outputs/<ID>`。

### Step 3：提取 PDF 文本（去掉参考文献）

提取全文后，裁掉末尾的 References/Bibliography 章节，避免浪费 context：

```bash
python -c "
import re, fitz

doc = fitz.open('outputs/<ID>/<ID>.pdf')
text = '\n'.join(page.get_text('text') for page in doc)
doc.close()

# ---- 裁掉参考文献章节（取最后一个匹配）----
# 匹配模式：行首的 References / Bibliography / REFERENCES，允许前有数字编号
ref_pattern = r'(?:^|\n)\s*(?:\d+\.?\s+)?(?:REFERENCES|References|Bibliography)\s*\n'
matches = list(re.finditer(ref_pattern, text, re.MULTILINE))
if matches:
    cut_pos = matches[-1].start()  # 最后一个匹配位置
    before = len(text)
    text = text[:cut_pos].rstrip()
    print(f'Stripped references: {before:,} → {len(text):,} chars (removed last {before - len(text):,} chars)')
else:
    print(f'No reference section detected, kept all {len(text):,} chars')

with open('outputs/<ID>/full_text.txt', 'w') as f:
    f.write(text)
"
```

### Step 4：提取论文元数据

从 PDF 文本前两页和文件名提取标题、作者等信息，用于填充报告头部。

### Step 5：生成 6 节精读报告

**关键约束**：
- **不要**把报告内容输出到对话中，只写入文件
- 每节按下方 prompt 要求撰写
- 完成后用一句话告知用户报告路径

逐节阅读 `full_text.txt`，按以下 6 个 prompt 依次生成各节内容，写入 `outputs/<ID>/report.md`。

---

## 报告模板与分节 Prompt

### 报告文件格式

```markdown
# {论文标题}

**作者**：{作者列表}
**发表时间**：{发表日期}
**Arxiv ID**：{arxiv_id}

---

## 1. 研究问题与动机

{第1节内容}

## 2. 核心方法

{第2节内容}

## 3. 实验设计与结果

{第3节内容}

## 4. 与相关工作的比较

{第4节内容}

## 5. 局限性与未来工作

{第5节内容}

## 6. 我的评价与启发

{第6节内容}
```

### 写作角色设定

你是一位资深 AI 研究员，正在为自己撰写论文精读笔记。写作要求：
- 语言为学术中文，表达精确，不啰嗦
- 用具体数字、公式、方法名支撑论点，不写空话
- 遇到方法细节时，解释清楚其设计动机，不只是罗列
- 不引用论文原文之外未出现的论文
- 所有数学公式必须使用 Markdown 格式：行内公式用 $...$，独立公式用 $$...$$

### 第 1 节：研究问题与动机（≥200 字）

撰写要点：
- 领域背景：该问题属于哪个研究方向，当前主流方法是什么
- 核心痛点：现有方法存在哪些根本性缺陷或局限
- 研究动机：作者为什么认为这个问题值得解决，重要性体现在哪里
- 论文目标：作者的核心 claim 是什么

### 第 2 节：核心方法（≥300 字）

撰写要点：
- 整体架构：方法的总体设计思路和模块划分
- 关键创新：与此前方法相比，最核心的技术创新是什么，解决了哪个具体问题
- 重要细节：关键模块的设计（可引用公式、超参数、算法步骤），并解释每个设计选择背后的动机
- 实现要点：训练策略、目标函数、推理方式中有哪些值得注意的地方

### 第 3 节：实验设计与结果（≥200 字）

撰写要点：
- 任务与数据集：评估了哪些任务，使用了哪些数据集，规模如何
- 基线选取：与哪些方法进行了比较，这些基线的选取是否合理
- 主要结果：关键指标上的具体数字，提升幅度是否显著
- 消融实验：哪些组件被单独验证，结论是什么
- 结果可信度：实验设计有无明显缺陷或遗漏

### 第 4 节：与相关工作的比较（≥200 字）

撰写要点：
- 优势：本文方法在哪些方面明显优于已有工作，技术层面的原因是什么
- 不足：相比相关工作，本文在哪些场景或指标上仍有差距
- 差异化：本文与最相近的工作的本质区别是什么

### 第 5 节：局限性与未来工作（≥150 字）

撰写要点：
- 作者承认的局限：论文中明确提到的不足或适用范围限制
- 未被承认的潜在问题：你认为该方法可能存在但作者未讨论的问题
- 未来工作：论文提出或你认为值得探索的后续研究方向，尽量具体

### 第 6 节：我的评价与启发（≥150 字）

撰写要点：
- 论文价值：这篇论文在领域内的贡献和地位如何
- 方法迁移：核心思路是否可以迁移到其他问题，如何迁移
- 对自己研究的启发：这篇论文给你带来了哪些具体的想法或新的研究问题

---

## 完成后

报告写入后，仅用一句话告知用户：
```
✅ report.md 已生成 → outputs/<ID>/report.md
```

**不要**将报告全文输出到对话中。
