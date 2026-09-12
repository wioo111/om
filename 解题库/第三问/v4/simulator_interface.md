# 第三问 · 模拟器接口预留

> 暂不实装模拟器对接；本文件给出接口约定与状态机，等接入模拟器时直接填实现。

## 1. 通信协议（参考附件 1）

```python
POST /enter                       → {"remaining_real_duration_s": N}
POST /measure   body={x, y, ch}   → {"measure_result": "direction"/"near"/"no_signal", "svd_deg": θ (only when direction)}
POST /clear     body={x, y, ch}   → {"clear_result": "success"/"no_target_in_range"}
POST /exit                          → {"reason": "user_exit" / ...}
```

## 2. 状态机

```
ENTER ──→ (检测循环) ──→ CLEAR ──→ (检测循环) ──→ ... ──→ EXIT
```

每个动作耗时由模拟器按前后位置 / 频道推断（附件 1 表 2）：
- 移动：`Δ距离 / 5 m/s`；
- 频道切换：1 秒（仅当 `ch_k ≠ ch_{k-1}`）；
- 检测 5 秒；清除未发现 3 秒，清除成功 5 秒。

## 3. 策略到指令的映射

- **闪烁跳跃**：每收一个 direction 即跳到下一个未清除频道的最近位置 → `MEASURE(new_pos, new_ch)`。
- **固定巡逻**：按预设路径 `[(x_1, y_1), ..., (x_K, y_K)]` 顺次扫描所有频道 → `MEASURE(road[k], ch[k])`。
- **静态扫描**：固定在 `P_0`，依次切换频道 → `MEASURE(P_0, ch)` for `ch ∈ C`。
- 无论哪种策略，定位收敛后都进入清除序列：`CLEAR(c_k*, ch)` → 若 success 则从 `R_t` 删去该频道，否则继续移动逼近。

## 4. 接入计划

待第一问、第二问验收后接入；接口封装在 `simulator_adapter.py`：
- `class Simulator` — 与 `http://127.0.0.1:2026` 通信
- 状态机：`enter → measure_loop → clear_loop → exit`
- 重试：网络异常时复用 request_id