# -*- coding: utf-8 -*-
"""统一结果信封与退出码（F01 整改）。

三类结果分开，不允许静态配置冒充处理结果：
  0 EXIT_OK          计算完成；数据本身可以是“不合格”，那不是错误。
  1 EXIT_RULE_FAILURE 业务规则判定拒绝（排名冲突、结构不安全、字段覆盖不全）。
  2 EXIT_INPUT_ERROR 输入非法（坏 JSON、缺字段、越界取值、类型错误）。

stdout 只写一个 JSON 对象；诊断信息写 stderr。中文按 UTF-8 字节写出，
不受控制台代码页影响。
"""

import json
import sys

EXIT_OK = 0
EXIT_RULE_FAILURE = 1
EXIT_INPUT_ERROR = 2

STATUS_OK = "OK"
STATUS_REJECTED = "REJECTED"
STATUS_INPUT_ERROR = "INPUT_ERROR"

SCHEMA = "wishcad.result.v1"


class InputError(ValueError):
    """输入不满足 schema 或取值域，退出码 2。"""

    def __init__(self, code, detail, path=None):
        self.code = code
        self.detail = detail
        self.path = path
        message = "%s: %s" % (code, detail)
        if path:
            message = "%s (%s)" % (message, path)
        super().__init__(message)


class RuleRejection(Exception):
    """业务规则拒绝，退出码 1。结果仍会完整输出，便于复核。"""

    def __init__(self, code, detail, data=None):
        self.code = code
        self.detail = detail
        self.data = data or {}
        super().__init__("%s: %s" % (code, detail))


def _write_json(obj, stream):
    text = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    target = getattr(stream, "buffer", None)
    if target is not None:
        stream.flush()
        target.write(text.encode("utf-8"))
        target.flush()
    else:
        stream.write(text)
        stream.flush()


def emit(module, status, exit_code, data=None, errors=None):
    """写一个信封对象到 stdout。"""
    payload = {
        "schema": SCHEMA,
        "module": module,
        "status": status,
        "exit_code": exit_code,
        "data": data if data is not None else {},
        "errors": errors or [],
    }
    _write_json(payload, sys.stdout)
    return exit_code


def emit_ok(module, data):
    """计算完成。`data["status"]` 若为 REJECTED/RANKING_CONFLICT 等业务拒绝态，
    由 `emit_data` 统一改判退出码 1，避免“规则拒绝却退 0”。"""
    return emit_data(module, data)


# 这些 data.status 表示“算完了但结论是拒绝/冲突”，应退 1 而不是 0。
RULE_REJECTION_STATUSES = frozenset({
    "REJECTED",
    "RANKING_CONFLICT",
    "NO_ELIGIBLE",
    "DIVERSITY_CONSTRAINED",
    "PAIRS_INCOMPLETE",
    "DIMENSIONS_INCOMPLETE",
})


def emit_data(module, data):
    """按 data.status 自动分层：业务拒绝态 → 退出码 1，其余 → 0。

    典型调用方是 scale/neutral/scoring 这类“返回结构化结论、不抛异常”的模块。
    scoring 的结论在 `data["ranking"]["status"]`，一并看。
    """
    status = data.get("status") if isinstance(data, dict) else None
    if status is None and isinstance(data, dict):
        ranking = data.get("ranking")
        if isinstance(ranking, dict):
            status = ranking.get("status")
    if status in RULE_REJECTION_STATUSES:
        payload = {
            "schema": SCHEMA,
            "module": module,
            "status": STATUS_REJECTED,
            "exit_code": EXIT_RULE_FAILURE,
            "data": data,
            "errors": [{"code": status,
                        "detail": "规则判定为 %s（见 data 内明细）" % status}],
        }
        sys.stderr.write("%s: %s\n" % (module, status))
        _write_json(payload, sys.stdout)
        return EXIT_RULE_FAILURE
    return emit_ok_raw(module, data)


def emit_ok_raw(module, data):
    return emit(module, STATUS_OK, EXIT_OK, data)


def emit_rejected(module, code, detail, data=None):
    sys.stderr.write("%s: %s\n" % (code, detail))
    return emit(module, STATUS_REJECTED, EXIT_RULE_FAILURE,
                data, [{"code": code, "detail": detail}])


def emit_input_error(module, code, detail, path=None):
    sys.stderr.write("%s: %s\n" % (code, detail))
    error = {"code": code, "detail": detail}
    if path:
        error["path"] = path
    return emit(module, STATUS_INPUT_ERROR, EXIT_INPUT_ERROR, {}, [error])


def load_json(path, module):
    """读入 JSON；坏文件与编码问题转成可读的 InputError。"""
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise InputError("CANNOT_READ_INPUT", str(exc), path)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError("INPUT_NOT_UTF8", str(exc), path)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise InputError("INVALID_JSON", str(exc), path)


def run_cli(module, runner, argv):
    """标准 CLI 外壳：读文件 → runner(payload) → 信封 → 退出码。

    runner 返回 data：按 `data.status` 分层（拒绝态退 1，其余退 0）；
    抛 RuleRejection → 退 1；抛 InputError → 退 2。--help 由 argparse 退 0。
    """
    try:
        payload = load_json(argv.path, module)
    except InputError as exc:
        return emit_input_error(module, exc.code, exc.detail, exc.path)
    try:
        data = runner(payload)
    except InputError as exc:
        return emit_input_error(module, exc.code, exc.detail, exc.path)
    except RuleRejection as exc:
        return emit_rejected(module, exc.code, exc.detail, exc.data)
    return emit_data(module, data)


def require_mapping(payload, key, module_path=None):
    """取一个必须是对象的字段。"""
    if not isinstance(payload, dict):
        raise InputError("NOT_AN_OBJECT", "顶层必须是 JSON 对象", module_path)
    if key not in payload:
        raise InputError("MISSING_FIELD", "缺少字段 %s" % key, module_path)
    value = payload[key]
    if not isinstance(value, dict):
        raise InputError("NOT_AN_OBJECT", "%s 必须是对象" % key, module_path)
    return value


def require_list(payload, key, module_path=None, allow_empty=True):
    if not isinstance(payload, dict):
        raise InputError("NOT_AN_OBJECT", "顶层必须是 JSON 对象", module_path)
    if key not in payload:
        raise InputError("MISSING_FIELD", "缺少字段 %s" % key, module_path)
    value = payload[key]
    if not isinstance(value, list):
        raise InputError("NOT_A_LIST", "%s 必须是数组" % key, module_path)
    if not allow_empty and not value:
        raise InputError("EMPTY_LIST", "%s 不能为空" % key, module_path)
    return value
