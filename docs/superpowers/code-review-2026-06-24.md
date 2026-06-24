# 代码审核报告 — 2026-06-24

**审查范围:** 未提交的修改（5 个文件, +19/-8 行）
**方法:** 8 角度查找 → 1 轮验证（recall-biased）

---

## 发现列表（按严重程度排序）

### 1. [HIGH] `TooManyConnectionsError` 未被捕获 → 连接池死锁

**文件:** [app/db.py:23-27](app/db.py#L23-L27)

**问题:** `except pymysql.Error` 不会捕获 `dbutils.pooled_db.TooManyConnectionsError`。该类继承自 `PooledDBError(Exception)`，**不是** `pymysql.Error` 的子类。当所有 10 个连接都被占用时，PooledDB 默认 `blocking=False`，直接抛出此异常 -> `_pool` 不被重置 -> 后续所有请求继续失败 -> 池永久死锁。

**复现场景:** Flask 默认开启线程模式。如果某时刻 11 个请求同时到达，或 `save_document()` 循环配合其他并发请求耗尽连接池，第 11 个请求将触发 `TooManyConnectionsError`，且永远不会恢复。

**修复建议:** 将 `except` 放宽为 `except (pymysql.Error, Exception)`，或同时捕获 `PooledDBError`；或传入 `blocking=True` 让连接池在耗尽时等待而非报错。

---

### 2. [HIGH] 全局变量 `_pool` 存在 TOCTOU 竞态条件

**文件:** [app/db.py:10-27](app/db.py#L10-L27)

**问题:** Flask 多线程模式下，`_pool` 的读（`if _pool is None`）和写（`_pool = PooledDB(...)` / `_pool = None`）未受锁保护。多个线程同时检查 `_pool` 会创建多个 PooledDB 实例（连接泄漏），或在错误-重置交织时出现 `_pool` 被设为 `None` 后另一线程仍试图调用 `.connection()` 导致 `AttributeError`。

**复现场景:** 高并发请求下，一个线程因网络错误设置 `_pool = None`，另一线程刚通过 `if _pool is None` 检查读到旧值，随后调用 `.connection()` 失败。或者懒初始化时两个线程创建了两个 pool。

**修复建议:** 添加 `threading.Lock()` 保护 `_pool` 的所有读写。

---

### 3. [MEDIUM] `_pool = None` 销毁池时连接泄漏

**文件:** [app/db.py:25-26](app/db.py#L25-L26)

**问题:** 任何 `pymysql.Error` 都将 `_pool` 设为 `None`，旧 PooledDB 对象被垃圾回收，但其管理的连接未被显式关闭。PooledDB 没有 `__del__` 方法来保证连接清理，导致 TCP 连接泄漏。

**复现场景:** MySQL 短暂重启后，所有新请求都要重新建池，而旧池的 10 个连接处于 TIME_WAIT 状态泄漏。

**修复建议:** 调用 `_pool._close()`（如果存在）或改用上下文管理器。更推荐不销毁整个池，而是逐连接验证（PooledDB 的 `ping=1` 参数）。

---

### 4. [MEDIUM] `process_unprocessed_docs` 返回值在 `with` 块外依赖局部变量

**文件:** [app/ingestion/pipeline.py:91](app/ingestion/pipeline.py#L91)

**问题:** `return len(docs)` 在 `with conn.cursor()` 上下文管理器之外引用 `docs`。当前 `fetchall()` 返回具体的 `list`，故能正确工作。但如果将来改为返回惰性游标/生成器，此行会崩溃。

**修复建议:** 将 `docs = cur.fetchall()` 的结果拷贝一份或在 `with` 块内赋值给外部变量。

---

### 5. [LOW] `save_news()` 中存在冗余的重复导入

**文件:** [app/data_providers/akshare_provider.py:128](app/data_providers/akshare_provider.py#L128)

**问题:** `from db import get_mysql` 已在模块顶部（第 10 行）导入，又在 `save_news()` 函数体内（第 128 行）重复导入。虽然 Python 缓存了 `sys.modules` 不会重新执行模块代码，但这是一个死代码/不一致问题。

**修复建议:** 删除第 128 行的重复导入。

---

### 6. [LOW] `REDIS_PASSWORD or None` 写法脆弱

**文件:** [app/db.py:34](app/db.py#L34)

**问题:** `Config.REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")` 总是返回字符串，用 `or None` 将空字符串转为 `None`。如果将来有人把 `config.py` 改为 `os.getenv("REDIS_PASSWORD")`（无默认值，返回 `None`），仍能工作但意图模糊。

**修复建议:** `config.py` 中直接默认 `None`：`REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")`；`db.py` 中直接用 `password=Config.REDIS_PASSWORD`。

---

## 架构层面观察（非 bug，但值得注意）

1. **路径计算重复 7+ 处:** `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` 在代码库中出现了 7 次以上，建议提取到 `config.py`。
2. **`app/__init__.py` 已设 CWD:** `app/__init__.py` 中 `os.chdir(Path(__file__).parent)` 让 `sys.path.insert(0, "..")` 不再需要——但 `app/` 下 6 个文件仍在使用。
3. **PooledDB 未启用 ping:** `PooledDB(ping=1)` 可以自动验证/重连失效的连接，当前未配置此参数。