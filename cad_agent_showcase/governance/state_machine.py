# -*- coding: utf-8 -*-
"""Canonical state and action mapping for the 25-state workflow.

Legacy aliases are recognized on input. Terminal states accept only
same-state receipts, and unknown actions are rejected.
"""

SCHEMA = "cad_state_mapping_v1"

# The 25 canonical workflow states in their original order.
CHAIN_STATES = (
    "FACTS_CLOSED",
    "ROLE_MATERIALS_READY",
    "DISPATCH_PLAN_READY_NOT_EXECUTED",
    "DESIGN_SESSION_RECEIPT_RECORDED",
    "DESIGN_COMPLETION_RECORDED",
    "JUDGE_PACKET_READY",
    "JUDGE_PLAN_READY_NOT_EXECUTED",
    "JUDGE_SESSION_RECEIPT_RECORDED",
    "解释先冻结",
    "评分/用户卡",
    "实际用户选择",
    "OUTBOX_READY_NOT_SENT",
    "SEND_RECEIPT_RECORDED_ACK_PENDING",
    "P_ACK_CONCEPT_START_REQUESTED",
    "RENDER_CLAIM_RECORDED",
    "概念视图",
    "标准交付",
    "AWAITING_MIN_DATA",
    "MIN_DATA_READY",
    "DESIGN_DRAWING_DELIVERED",
    "AWAITING_MANUFACTURING_CONSENT",
    "MANUFACTURING_CONSENT_RECORDED",
    "DEVELOPMENT_OUTPUT_DELIVERED",
    "CONCEPT_ONLY_CLOSED",
    "DESIGN_ONLY_CLOSED",
)

TERMINAL_STATES = (
    "DEVELOPMENT_OUTPUT_DELIVERED",
    "CONCEPT_ONLY_CLOSED",
    "DESIGN_ONLY_CLOSED",
)

# 旧别名只读：只在读取旧记录时规范化，新输出一律写规范名。
ALIASES = {
    "MIN_DATA_RECORDED": "MIN_DATA_READY",
    "CONCEPT_ENDPOINT_HELD": "CONCEPT_ONLY_CLOSED",
}

# 合法迁移：§1 链 + §2 表；标准交付两条按模式区分，§1.2 的 G1 退回同走 AWAITING_MIN_DATA。
TRANSITIONS = {
    "FACTS_CLOSED": ("ROLE_MATERIALS_READY",),
    "ROLE_MATERIALS_READY": ("DISPATCH_PLAN_READY_NOT_EXECUTED",),
    "DISPATCH_PLAN_READY_NOT_EXECUTED": ("DESIGN_SESSION_RECEIPT_RECORDED",),
    "DESIGN_SESSION_RECEIPT_RECORDED": ("DESIGN_COMPLETION_RECORDED",),
    "DESIGN_COMPLETION_RECORDED": ("JUDGE_PACKET_READY",),
    "JUDGE_PACKET_READY": ("JUDGE_PLAN_READY_NOT_EXECUTED",),
    "JUDGE_PLAN_READY_NOT_EXECUTED": ("JUDGE_SESSION_RECEIPT_RECORDED",),
    "JUDGE_SESSION_RECEIPT_RECORDED": ("解释先冻结",),
    "解释先冻结": ("评分/用户卡",),
    "评分/用户卡": ("实际用户选择",),
    "实际用户选择": ("OUTBOX_READY_NOT_SENT",),
    "OUTBOX_READY_NOT_SENT": ("SEND_RECEIPT_RECORDED_ACK_PENDING",),
    "SEND_RECEIPT_RECORDED_ACK_PENDING": ("P_ACK_CONCEPT_START_REQUESTED",),
    "P_ACK_CONCEPT_START_REQUESTED": ("RENDER_CLAIM_RECORDED",),
    "RENDER_CLAIM_RECORDED": ("概念视图",),
    "概念视图": ("标准交付",),
    "标准交付": ("AWAITING_MIN_DATA", "AWAITING_MANUFACTURING_CONSENT"),
    "AWAITING_MIN_DATA": ("MIN_DATA_READY", "CONCEPT_ONLY_CLOSED"),
    "MIN_DATA_READY": ("DESIGN_DRAWING_DELIVERED",),
    "DESIGN_DRAWING_DELIVERED": ("AWAITING_MANUFACTURING_CONSENT",),
    "AWAITING_MANUFACTURING_CONSENT": ("MANUFACTURING_CONSENT_RECORDED",
                                       "DESIGN_ONLY_CLOSED"),
    "MANUFACTURING_CONSENT_RECORDED": ("DEVELOPMENT_OUTPUT_DELIVERED",),
    "DEVELOPMENT_OUTPUT_DELIVERED": (),
    "CONCEPT_ONLY_CLOSED": (),
    "DESIGN_ONLY_CLOSED": (),
}

EDGE_REASONS = {
    ("标准交付", "AWAITING_MIN_DATA"):
        "LEGAL_EDGE_CONCEPT_LINE_OR_G1_FALLBACK",
    ("标准交付", "AWAITING_MANUFACTURING_CONSENT"):
        "LEGAL_EDGE_DRAWING_LINE",
    ("AWAITING_MIN_DATA", "CONCEPT_ONLY_CLOSED"):
        "LEGAL_EDGE_REJECT_TERMINAL_CONCEPT_ONLY",
    ("AWAITING_MANUFACTURING_CONSENT", "DESIGN_ONLY_CLOSED"):
        "LEGAL_EDGE_REJECT_TERMINAL_DESIGN_ONLY",
}

# 非链上动作状态 → 链上状态或 ACTION_*（动作级，不是链上节点）。
# 25 个链上状态本身也接受为 action_status，按同名映射（见 resolve_action_status）。
ACTION_STATUS_MAP = {
    # gates：链上节点
    "AWAITING_MIN_DATA": "AWAITING_MIN_DATA",
    "MIN_DATA_READY": "MIN_DATA_READY",
    "CONCEPT_ONLY_CLOSED": "CONCEPT_ONLY_CLOSED",
    "DESIGN_DRAWING_DELIVERED": "DESIGN_DRAWING_DELIVERED",
    "AWAITING_MANUFACTURING_CONSENT": "AWAITING_MANUFACTURING_CONSENT",
    "MANUFACTURING_CONSENT_RECORDED": "MANUFACTURING_CONSENT_RECORDED",
    "DESIGN_ONLY_CLOSED": "DESIGN_ONLY_CLOSED",
    # gates：动作级回执
    "CONCEPT_CAD_PENDING": "ACTION_CONCEPT_CAD_PENDING",
    "SCOPE_AND_CAPABILITY_READY": "ACTION_SCOPE_AND_CAPABILITY_READY",
    "OK": "ACTION_OK",
    "MIN_DATASET_INCOMPLETE": "ACTION_MIN_DATASET_INCOMPLETE",
    "INVALIDATED": "ACTION_CONFIRMATION_INVALIDATED",
    "CONFIRMATION_INVALIDATED": "ACTION_CONFIRMATION_INVALIDATED",
    # integration：单次动作返回
    "MANUFACTURING_PREVIEW_DELIVERED": "ACTION_MANUFACTURING_PREVIEW_DELIVERED",
    "STOPPED": "ACTION_STOPPED",
    "INPUT_ERROR": "ACTION_INPUT_ERROR",
    "INTERNAL_ERROR": "ACTION_INTERNAL_ERROR",
    # 后端：动作级返回
    "SOURCE_PREPARED_REVIEW_REQUIRED": "ACTION_SOURCE_PREPARED_REVIEW_REQUIRED",
    "DEV_GRAPH_READY": "ACTION_DEV_GRAPH_READY",
    "DEV_MODEL_CHECKED": "ACTION_DEV_MODEL_CHECKED",
    "DEV_DESIGN_PROPOSAL": "ACTION_DEV_DESIGN_PROPOSAL",
    "BLOCKED": "ACTION_BLOCKED",
    "REJECTED": "ACTION_REJECTED",
    "LOCAL_CHECK_PASSED": "ACTION_LOCAL_CHECK_PASSED",
    # Review and measurement action outcomes.
    "REVIEW_WORKPACK_PREPARED": "ACTION_REVIEW_WORKPACK_PREPARED",
    "PENDING_REVIEW": "ACTION_PENDING_REVIEW",
    "CANDIDATE_COMPLETE_PENDING_ENGINEERING":
        "ACTION_CANDIDATE_COMPLETE_PENDING_ENGINEERING",
    "T05_CAMPAIGN_CREATED": "ACTION_T05_CAMPAIGN_CREATED",
    "INTERRUPTED": "ACTION_INTERRUPTED",
    "T05_ATTEMPT_RECORDED": "ACTION_T05_ATTEMPT_RECORDED",
    "T05_ABORT_RECORDED_NO_REFUND": "ACTION_T05_ABORT_RECORDED_NO_REFUND",
    # The confirmation ledger does not advance the workflow.
    "UNCHANGED": "ACTION_CONFIRMATION_UNCHANGED",
    # 状态机 §1.3：明确不进链的回执状态
    "P_ROUTE_REGISTERED": "ACTION_P_ROUTE_REGISTERED",
    "RETURN_ROUTE_READY": "ACTION_RETURN_ROUTE_READY",
    "SESSION_EVIDENCE_REVIEWED": "ACTION_SESSION_EVIDENCE_REVIEWED",
    "START_CLAIMED": "ACTION_START_CLAIMED",
    "START_ALREADY_CLAIMED": "ACTION_START_ALREADY_CLAIMED",
    "SESSION_ALREADY_BOUND": "ACTION_SESSION_ALREADY_BOUND",
    "FEEDBACK_CANDIDATE_RECORDED": "ACTION_FEEDBACK_CANDIDATE_RECORDED",
    "TIMING_RECORDED": "ACTION_TIMING_RECORDED",
}


def state_result():
    return {
        "schema": SCHEMA,
        "status": "OK",
        "previous_state": None,
        "action_status": None,
        "chain_state": None,
        "canonical_state": None,
        "alias_used": False,
        "transition": {"allowed": False, "reason": "UNEVALUATED"},
        "terminal": False,
        "engineering_approval": False,
        "production_approved": False,
        "can_enter_p2": False,
    }


def _reject(result, code, detail, reason):
    result["status"] = "REJECTED"
    result["code"] = code
    result["detail"] = detail
    result["transition"] = {"allowed": False, "reason": reason}
    return result, 2


def normalise_state(value):
    text = value.strip()
    if text in ALIASES:
        return ALIASES[text], True
    return text, False


def resolve_action_status(value):
    canonical, alias_used = normalise_state(value)
    if canonical in ACTION_STATUS_MAP or canonical in CHAIN_STATES:
        return canonical, alias_used
    return None, alias_used


def evaluate(payload):
    """单次映射：动作状态 → 链上节点或 ACTION_*，并核对迁移。

    - 只有两个链上状态之间的边才可能 allowed=true；同名回执记为 SAME_STATE_NOOP。
    - 动作级状态不推进链路；INVALIDATED 额外标记 confirmation_invalidated 与
      re_review_required，且不改 chain_state。
    - 终点只接受同名回执；任何不同名目标给 STATE_TERMINAL_NO_TRANSITION。
    """
    result = state_result()
    if not isinstance(payload, dict):
        return _reject(result, "STATE_PAYLOAD_INVALID",
                       "payload 必须是 JSON 对象", "PAYLOAD_INVALID")
    evidence = payload.get("evidence")
    if evidence is not None and not isinstance(evidence, dict):
        return _reject(result, "STATE_PAYLOAD_INVALID",
                       "evidence 必须是 JSON 对象", "PAYLOAD_INVALID")

    raw_action = payload.get("action_status")
    if not isinstance(raw_action, str) or not raw_action.strip():
        return _reject(result, "STATE_ACTION_STATUS_REQUIRED",
                       "payload.action_status 必须是非空字符串",
                       "ACTION_STATUS_REQUIRED")
    action_status, alias_used = resolve_action_status(raw_action)
    if action_status is None:
        result["action_status"] = raw_action.strip()
        return _reject(result, "STATE_UNKNOWN_ACTION_STATUS",
                       "未知动作状态：%s" % raw_action.strip(),
                       "UNKNOWN_ACTION_STATUS")
    result["action_status"] = action_status
    result["alias_used"] = alias_used

    raw_previous = payload.get("previous_state")
    previous = None
    previous_kind = "absent"
    if raw_previous is not None:
        if not isinstance(raw_previous, str) or not raw_previous.strip():
            return _reject(result, "STATE_UNKNOWN_PREVIOUS_STATE",
                           "previous_state 必须是非空字符串或省略",
                           "UNKNOWN_PREVIOUS_STATE")
        previous, previous_alias = normalise_state(raw_previous)
        result["alias_used"] = result["alias_used"] or previous_alias
        result["previous_state"] = previous
        if previous in CHAIN_STATES:
            previous_kind = "chain"
        elif previous in ACTION_STATUS_MAP:
            previous_kind = "action"
        else:
            return _reject(result, "STATE_UNKNOWN_PREVIOUS_STATE",
                           "未知 previous_state：%s" % previous,
                           "UNKNOWN_PREVIOUS_STATE")

    canonical = ACTION_STATUS_MAP.get(action_status, action_status)
    result["canonical_state"] = canonical
    is_chain = canonical in CHAIN_STATES
    result["chain_state"] = canonical if is_chain else (
        previous if previous_kind == "chain" else None)
    result["terminal"] = (canonical in TERMINAL_STATES if is_chain else
                          (previous in TERMINAL_STATES
                           if previous_kind == "chain" else False))

    if previous_kind == "chain" and previous in TERMINAL_STATES \
            and canonical != previous:
        result["chain_state"] = previous
        result["terminal"] = True
        return _reject(result, "STATE_TERMINAL_NO_TRANSITION",
                       "终点后不得继续：%s → %s" % (previous, canonical),
                       "TERMINAL_NO_TRANSITION")

    if canonical == "ACTION_CONFIRMATION_INVALIDATED":
        result["confirmation_invalidated"] = True
        result["re_review_required"] = True
        result["chain_state"] = previous if previous_kind == "chain" else None
        result["terminal"] = (previous in TERMINAL_STATES
                              if previous_kind == "chain" else False)
        result["transition"] = {"allowed": False,
                                "reason": "CONFIRMATION_INVALIDATED_NO_ADVANCE"}
        return result, 0

    if is_chain:
        if previous_kind == "absent":
            result["transition"] = {"allowed": False,
                                    "reason": "PREVIOUS_STATE_NOT_PROVIDED"}
            return result, 0
        if previous_kind == "action":
            result["transition"] = {
                "allowed": False,
                "reason": "PREVIOUS_STATE_ACTION_LEVEL_UNVERIFIED"}
            return result, 0
        if previous == canonical:
            result["transition"] = {"allowed": True,
                                    "reason": "SAME_STATE_NOOP"}
            return result, 0
        if canonical in TRANSITIONS.get(previous, ()):
            result["transition"] = {
                "allowed": True,
                "reason": EDGE_REASONS.get((previous, canonical), "LEGAL_EDGE")}
            return result, 0
        result["chain_state"] = previous
        result["terminal"] = previous in TERMINAL_STATES
        return _reject(result, "STATE_TRANSITION_NOT_ALLOWED",
                       "非法迁移：%s → %s" % (previous, canonical),
                       "ILLEGAL_TRANSITION")

    result["transition"] = {"allowed": False,
                            "reason": "ACTION_LEVEL_NOT_CHAIN_STATE"}
    return result, 0


def annotate(target, action_status, previous_state=None):
    """把映射结果附加到调用方动作结果上；不改变原结果字段与语义。

    生产调用方只读这些 `chain_*` 字段；动作级状态不会推进 `chain_state`。
    """
    mapped, _code = evaluate({"previous_state": previous_state,
                              "action_status": action_status})
    target["chain_state"] = mapped.get("chain_state")
    target["chain_previous_state"] = mapped.get("previous_state")
    target["chain_transition"] = mapped.get("transition")
    target["chain_mapping_status"] = mapped.get("status")
    target["chain_canonical_state"] = mapped.get("canonical_state")
    target["chain_alias_used"] = mapped.get("alias_used", False)
    if mapped.get("status") != "OK":
        target["chain_error"] = mapped.get("code")
    return target
