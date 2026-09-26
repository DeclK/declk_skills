---
name: npu-monitor
description: 监控和分析 NPU AI Core 显著低利用率。无参数时启动 npu_monitor.py 采集，给 CSV 时运行 npu_analyze.py 分析并画图。用户可调用 /npu-monitor 来激活。
user-invocable: true
argument-hint: "[csv_file | monitor_options]"
allowed-tools: "Bash"
---

# NPU Monitor — 监控与分析 NPU AI Core 利用率

启动 npu-smi 利用率采集或分析采集到的 CSV 数据。

## 参数

- `$ARGUMENTS`: 
  - **无参数** 或 **不是 .csv 结尾的参数**：启动监控模式，所有参数透传给 `npu_monitor.py`
  - **第一个参数是 .csv 文件**：进入分析模式，CSV 路径及其余参数透传给 `npu_analyze.py`

## 执行流程

### Step 1: 判断模式

```bash
FIRST_ARG=$(echo "$ARGUMENTS" | awk '{print $1}')
SCRIPT_DIR="$SKILL_DIR/scripts"

if [ -z "$FIRST_ARG" ]; then
    MODE="monitor"
elif echo "$FIRST_ARG" | grep -q '\.csv$'; then
    MODE="analyze"
    CSV_FILE="$FIRST_ARG"
    # 剩下的参数（去掉第一个）
    REST_ARGS=$(echo "$ARGUMENTS" | sed "s/^[^ ]* *//")
else
    MODE="monitor"
fi
```

### Step 2: 执行对应脚本

**监控模式：**

```bash
python "$SCRIPT_DIR/npu_monitor.py" $ARGUMENTS
```

按 `Ctrl+C` 可随时停止采集。

**分析模式：**

```bash
python "$SCRIPT_DIR/npu_analyze.py" "$CSV_FILE" $REST_ARGS
```

分析完成后自动在同目录生成 `.png` 折线图。

## 常用示例

```bash
# 启动监控，默认 1s 间隔
/npu-monitor

# 监控，自定义间隔和设备
/npu-monitor --interval 2 --devices 0,1,2,3

# 分析 CSV（默认全卡、20% 阈值、自动画图）
/npu-monitor npu_usage_20260706_161059.csv

# 分析 CSV + 跳过冷启动 60s + 只看 4 张卡
/npu-monitor npu_usage_20260706_161059.csv --skip 60 --devices 0,1,2,3

# 分析 CSV + 自定义低利用率阈值
/npu-monitor npu_usage_20260706_161059.csv --threshold 15

# 分析 CSV + 限制最大采样点数（均匀降采样）
/npu-monitor npu_usage_20260706_161059.csv --max-samples 1000
```
