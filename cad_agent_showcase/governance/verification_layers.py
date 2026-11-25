# -*- coding: utf-8 -*-
"""Five-layer verification report and additive failure-layer summary (Q3/K1/K2).

Nothing here changes the original error codes or the backend checks. The layer
projection is a summary contract; when a mapping is missing it is listed as a
gap instead of being guessed.
"""
from .envelope import InputError

SCHEMA = "wishcad.verification-layers.v1"
LAYERS = (
    ("L1", "构造读回", "backend"),
    ("L2", "本次尺寸单位对象装拆", "designer"),
    ("L3", "受控参数域重建", "backend"),
    ("L4", "目标消费端解析", "judge"),
    ("L5", "工程批准", "user"),
)
STATUSES = ("PASS", "FAIL", "NOT_RUN", "NOT_APPLICABLE")
INDEPENDENCE = ("SAME_CORE", "INDEPENDENT", "NOT_APPLICABLE")

# Original codes stay untouched; this table only adds a layer and a minimal recovery.
FAILURE_LAYER_MAP = {
    "DRAWING_LAYOUT_OVERFLOW": ("L3", "按图幅规则调整视图或缩小件，超 A0 只列方案"),
    "CUT_OVERLAP": ("L3", "修几何重叠后重跑受管构造"),
    "CUT_TANGENT_SIDE_UNSUPPORTED": ("L3", "孔槽直边相切不支持，改几何后重跑"),
    "CAPABILITY_CARD_MISSING": ("L3", "恢复后端能力卡后重跑"),
    "RELATION_SWAP_MISMATCH": ("L2", "重复阵列关联对调：形状可读，但关联核验阻断；重绑定义点/handle 后复查"),
    "SEMANTIC_CHECK_INVALID": ("L4", "修标注后重跑独立核对"),
    "FORMAL_COMPARISON_STALE": ("L4", "按当前冻结输入重算比较卡"),
}
FAILURE_PREFIXES = (
    ("SEMANTIC_", ("L4", "修标注后重跑独立核对")),
    ("CUT_", ("L3", "修几何后重跑受管构造")),
)
STAGE_LAYERS = (("concept_render", "L1"), ("backend", "L3"), ("delivery", "L4"), ("compare", "L4"))

TIERS = {
    "概念方案": {"can_do": "概念视图、方案比较、条件稿", "evidence": "渲染与语义记录；不含构造读回",
                 "owner": "P/D/J0（开发预览）"},
    "受支持板件设计图": {"can_do": "后端四操作子集内的板件设计图", "evidence": "构造读回、定义点/页/handle 核对",
                          "owner": "后端与设计席；工程批准仍缺"},
    "开发输出": {"can_do": "开发档成品图运行与评审", "evidence": "运行清单与独立核对；DEVELOPMENT FIXTURE",
                 "owner": "开发侧；不构成生产批准"},
}


def build(layers=None):
    """Return the fixed five-layer report; unknown input entries are rejected."""
    provided = {}
    for row in layers or []:
        if not isinstance(row, dict) or row.get("id") not in dict((item[0], item) for item in LAYERS):
            raise InputError("VERIFICATION_LAYER_INVALID", "层 id 必须为 L1–L5")
        provided[row["id"]] = row
    output = []
    for layer_id, name, owner in LAYERS:
        row = provided.get(layer_id, {})
        status = row.get("status", "NOT_RUN")
        if status not in STATUSES:
            raise InputError("VERIFICATION_LAYER_INVALID", "层状态非法：" + str(status))
        independence = row.get("independence", "NOT_APPLICABLE")
        if independence not in INDEPENDENCE:
            raise InputError("VERIFICATION_LAYER_INVALID", "同核/独立标识非法：" + str(independence))
        output.append({"id": layer_id, "name": name, "status": status,
                       "evidence_refs": row.get("evidence_refs", []),
                       "independence": independence, "owner": row.get("owner", owner),
                       "gaps": row.get("gaps", [])})
    return {"schema": SCHEMA, "layers": output, "engineering_approval": False}


def classify(code, stage=None):
    """Map an original code to a layer without changing the code itself."""
    if not isinstance(code, str) or not code:
        raise InputError("FAILURE_CODE_INVALID", "错误码须为非空字符串")
    if code == "GEOMETRY_UNSUPPORTED":
        if stage == "concept_render":
            return {"code": code, "layer": "L1",
                    "minimal_recovery": "检查五类图元与尺寸，改概念表达或缩小范围"}
        return {"code": code, "layer": "L3",
                "minimal_recovery": "按能力快照核对操作/尺寸/图幅；缺映射只列缺口"}
    if code == "STAGE_FAILED":
        layer = dict(STAGE_LAYERS).get(stage)
        if layer is None and isinstance(stage, str):
            text = stage.lower()
            if "render" in text:
                layer = "L1"
            elif any(key in text for key in ("dxf", "model", "geo", "build", "verify")):
                layer = "L3"
            elif any(key in text for key in ("semantic", "annot", "delivery", "compare")):
                layer = "L4"
        if layer:
            return {"code": code, "layer": layer,
                    "minimal_recovery": "保留 STAGE_FAILED 匹配语义；按阶段定位后重跑该阶段"}
        return {"code": code, "layer": None, "minimal_recovery": None,
                "note": "STAGE_FAILED 未给可映射 stage：只列缺口，不猜层"}
    if code in FAILURE_LAYER_MAP:
        layer, recovery = FAILURE_LAYER_MAP[code]
        return {"code": code, "layer": layer, "minimal_recovery": recovery}
    for prefix, (layer, recovery) in FAILURE_PREFIXES:
        if code.startswith(prefix):
            return {"code": code, "layer": layer, "minimal_recovery": recovery}
    return {"code": code, "layer": None, "minimal_recovery": None,
            "note": "未映射：只列缺口，不猜层"}


def failure_summary(errors):
    """errors: [{"code": str, "stage": str|None}] -> additive summary rows."""
    if errors is None:
        items = []
    elif isinstance(errors, list):
        items = errors
    else:
        raise InputError("FAILURE_CODE_INVALID", "failure_layers 须为对象数组")
    rows = []
    for item in items:
        if not isinstance(item, dict):
            raise InputError("FAILURE_CODE_INVALID", "failure_layers 条目须为对象")
        rows.append(classify(item.get("code"), item.get("stage")))
    return {"original_codes_unchanged": True, "rows": rows,
            "unmapped": [row["code"] for row in rows if row["layer"] is None]}
