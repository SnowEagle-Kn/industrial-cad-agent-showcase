# -*- coding: utf-8 -*-
"""公共事实包中性审查与事实轮关闭判定。

关键词表只是辅助，本模块不是语义证明：它只能抓到表内的预选构型措辞，
抓不到改写、隐晦暗示和图示里的结构答案。PASS 只表示“表内未命中”，
不证明公共包中性。语义中性由人审，本模块不声称已验证。

F07 整改：
  * 事实轮关闭拆成两件事——**是否收到一次有效作答**与**答案内容**。
    非空作答即关闭一轮，未答项保留 UNKNOWN；“没有/不清楚/按现有材料做”
    一类同义表述只影响 closure_reason，不影响是否关闭。
  * 空白/纯空白不算作答，不关闭，也不当成“否”。
  * max_rounds=1：关闭后 D/J0 再提问只能登记为内部未知，不发第二轮。
"""

import argparse
import re

from .envelope import InputError

# 关键词只作辅助命中，漏报不代表没有结构答案。
_STRUCTURE_HINTS = (
    "双立柱", "单立柱", "门架", "悬臂", "龙门", "桁架", "三角支撑",
    "四连杆", "连杆", "导轨", "滑台", "丝杠", "气缸", "液压",
    "焊接支架", "铸造支架", "折弯件", "型材框架",
)
_LEADING_MARKERS = ("采用", "用", "选用", "改用", "换成", "使用", "做成", "设计成")
_ASKING_MARKERS = ("好吗", "行吗", "可以吗", "是否", "是不是", "要不要", "如何", "怎么样")

_INSTRUCTION_LEAK_RE = re.compile(r"忽略规则|忽略以上|ignore\s+rules", re.IGNORECASE)


def _source_is_user_fact(item):
    source = item.get("source") or item.get("source_ref") or ""
    status = item.get("evidence_status") or item.get("status") or ""
    return source == "USER_FACT" or status == "USER_FACT"


def _scan_text(text):
    """返回命中的关键词。不是语义判断，只是子串命中。"""
    hits = []
    for hint in _STRUCTURE_HINTS:
        if hint not in text:
            continue
        window_start = max(0, text.find(hint) - 6)
        window = text[window_start:text.find(hint) + len(hint) + 6]
        led = any(marker in window for marker in _LEADING_MARKERS)
        asked = any(marker in text for marker in _ASKING_MARKERS)
        if led or asked:
            hits.append(hint)
    return hits


def review_packet(packet):
    """审查公共事实包是否夹带结构答案。

    用户原文里明确要求的结构（source 或 evidence_status 标记 USER_FACT）
    保留来源，不算泄露。其余字段与追问文本按关键词辅助检查。
    """
    if not isinstance(packet, dict):
        raise TypeError("packet 必须是 dict")
    findings = []

    def walk(node, path):
        if isinstance(node, dict):
            if _source_is_user_fact(node):
                return
            for key, value in node.items():
                walk(value, path + [str(key)])
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + [str(index)])
        elif isinstance(node, str):
            for hint in _scan_text(node):
                findings.append({
                    "path": "/".join(path),
                    "hint": hint,
                    "excerpt": node[:80],
                    "kind": "structure_preselection",
                })
            if _INSTRUCTION_LEAK_RE.search(node):
                findings.append({
                    "path": "/".join(path),
                    "hint": "instruction_text",
                    "excerpt": node[:80],
                    "kind": "embedded_instruction_registered_not_executed",
                })

    walk(packet, [])
    leaked = any(item["kind"] == "structure_preselection" for item in findings)
    return {
        "status": "REJECTED" if leaked else "PASS",
        "design_answer_in_public_packet": leaked,
        "findings": findings,
        "keyword_table_is_semantic_proof": False,
    }


# ---------------------------------------------------------------- F07
# “没有资料”同义表述。长词在前，命中后取最长的一条作为 closure_phrase。
NO_MORE_EVIDENCE_PHRASES = (
    "没有更多资料", "没有其他资料", "没有其它资料", "没有其他信息",
    "没有其它信息", "没有更多信息", "没有更多补充", "没有其他补充",
    "按现有材料做", "按现有资料做", "按现有材料来", "按现有材料",
    "按图纸做", "按图做", "按图来", "按图",
    "没有资料", "没有数据", "没有尺寸", "没有信息", "没有补充",
    "没有具体尺寸", "没有测过", "没测过", "未测量", "没量过",
    "无法确认", "无法提供", "没法确认", "没办法确认",
    "不知道尺寸", "不清楚尺寸", "不知道具体尺寸",
    "没资料", "无资料", "暂无资料", "暂无数据", "暂时没有", "暂时没有资料",
    "没有了", "没有", "没", "无",
    "不清楚", "不知道", "不确定", "不了解",
    "暂无", "没有别的", "没有其它", "没有其他",
)

# 判定“这句话是不是纯属无资料答复”时允许留下的填充词。
_FILLER_CHARS = set(
    "的了吗呢啊吧呀嘛是在也都就还再要问这那个项条点些里"
    "，。、,.;；：:！!？?（）()【】[]{}<>《》\"'　 \t\r\n"
)
_FILLER_WORDS = (
    "尺寸", "资料", "数据", "信息", "情况", "方面", "其他", "其它",
    "更多", "补充", "别的", "现有", "材料", "图纸", "图", "做", "来",
    "说", "暂时", "暂", "还", "都", "也",
)

CLOSURE_USER_ANSWERED = "USER_ANSWERED"
CLOSURE_NO_MORE_EVIDENCE = "USER_HAS_NO_MORE_EVIDENCE"
CLOSURE_SUPPLEMENT = "USER_SUPPLEMENT_AFTER_CLOSURE"


def _match_phrases(text):
    """子串命中同义表，返回按长度降序的命中词。"""
    hits = [phrase for phrase in NO_MORE_EVIDENCE_PHRASES if phrase in text]
    return sorted(set(hits), key=len, reverse=True)


def _is_pure_no_more_evidence(compact, matched):
    """整句只由“无资料”表述加填充词组成，才算纯无资料答复。

    “地面已调平，宽度800毫米，高度不清楚”含“不清楚”但另有实质事实，
    因此不是纯无资料答复，按正常作答关闭（未答项仍记 UNKNOWN）。
    """
    if not matched:
        return False
    rest = compact
    for phrase in matched:
        rest = rest.replace(phrase, "")
    changed = True
    while changed:
        changed = False
        for word in _FILLER_WORDS:
            if word in rest:
                rest = rest.replace(word, "")
                changed = True
    return all(char in _FILLER_CHARS for char in rest)


def _as_item_list(value, field):
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise InputError("ITEMS_NOT_A_LIST", "%s 必须是数组" % field)
    items = []
    for index, entry in enumerate(value):
        if isinstance(entry, dict):
            name = entry.get("item") or entry.get("name")
        else:
            name = entry
        if name is None or str(name).strip() == "":
            raise InputError("ITEM_NAME_EMPTY",
                             "%s[%d] 缺名称" % (field, index))
        items.append(str(name))
    return items


def close_fact_round(answer_text, unanswered_items=None, answered_items=None,
                     sent_rounds=1, max_rounds=1, supplement_text=None):
    """一轮事实追问的关闭判定。

    关闭与否只看**是否收到一次非空作答**；答案内容只决定 closure_reason。
    未答不是否：空白作答不关闭，未答项一律 UNKNOWN。
    max_rounds=1：关闭后不再发第二轮，后续主动补充只升级事实包。
    """
    if answer_text is None:
        answer_text = ""
    if not isinstance(answer_text, str):
        raise InputError("ANSWER_NOT_TEXT", "answer_text 必须是字符串")
    if supplement_text is not None and not isinstance(supplement_text, str):
        raise InputError("SUPPLEMENT_NOT_TEXT", "supplement_text 必须是字符串")
    try:
        sent = int(sent_rounds)
        maximum = int(max_rounds)
    except (TypeError, ValueError):
        raise InputError("ROUNDS_NOT_INT", "sent_rounds / max_rounds 必须是整数")
    if sent < 0:
        raise InputError("ROUNDS_NEGATIVE", "sent_rounds 不能为负")
    if maximum < 1:
        raise InputError("MAX_ROUNDS_INVALID", "max_rounds 至少为 1（合同值为 1）")

    text = answer_text.strip()
    supplement = (supplement_text or "").strip()
    unanswered = _as_item_list(unanswered_items, "unanswered_items")
    answered = _as_item_list(answered_items, "answered_items")

    matched = _match_phrases(text)
    compact = re.sub(r"\s+", "", text)
    pure_no_more = _is_pure_no_more_evidence(compact, matched)

    result = {
        "closed": False,
        "dispatch_readiness": "SEPARATE_REQUIREMENTS_CONSUMER_REQUIRED",
        "closure_reason": None,
        "closure_phrase": None,
        "matched_phrases": matched,
        "answer_is_blank": not text,
        "unanswered_is_not_no": True,
        "inferred_ground_or_budget": False,
        "rounds_used": 0,
        "max_rounds": maximum,
        "second_round_forbidden": False,
        "unresolved_items": list(unanswered),
        "unresolved_item_records": [{"item": name, "status": "UNKNOWN"}
                                    for name in unanswered],
        "answered_items": list(answered),
        "answered_item_records": [{"item": name, "status": "ANSWERED"}
                                  for name in answered],
        "supplement_registered": bool(supplement),
        "supplement_upgrades_packet": bool(supplement),
        "new_round_sent": False,
        "note": "",
    }

    if not text:
        result["second_round_forbidden"] = sent >= maximum
        if supplement:
            result["note"] = ("本轮未收到作答，事实轮保持未关闭；用户主动补充只升级事实包，"
                              "不算作答、不重开一轮追问")
        else:
            result["note"] = "未答不是否；空白作答不关闭事实轮，本轮仍在等待用户作答"
        return result

    result["closed"] = True
    # rounds_used 如实记“实际发出过几轮”，不把 0 改写成 1（P2-04）。
    # “从未追问却有作答”是输入矛盾，单独标出，由调用方核对，不静默圆场。
    result["rounds_used"] = sent
    contradiction = None
    if sent == 0:
        contradiction = "ANSWER_WITHOUT_SENT_ROUND"
        result["input_contradiction"] = contradiction
    result["second_round_forbidden"] = True
    if pure_no_more:
        answer_reason = CLOSURE_NO_MORE_EVIDENCE
        result["closure_phrase"] = matched[0] if matched else None
        result["note"] = ("用户明确无更多资料（命中“%s”），事实轮关闭；"
                          "未答项保留 UNKNOWN，不当作否" % result["closure_phrase"])
    else:
        answer_reason = CLOSURE_USER_ANSWERED
        if matched:
            result["closure_phrase"] = matched[0]
            result["note"] = ("收到一次有效作答，事实轮关闭；文中含“%s”只说明该项无资料，"
                              "未答项保留 UNKNOWN" % matched[0])
        else:
            result["note"] = "收到一次有效作答，事实轮关闭；未答项保留 UNKNOWN"
    if contradiction:
        result["note"] += ("；但 sent_rounds=0（从未发出追问），"
                           "该作答的来源须核对，rounds_used 保持 0")
    result["answer_closure_reason"] = answer_reason
    if supplement:
        # 主动补充发生在事实轮之后：只升级事实包，不重开一轮追问。
        result["closure_reason"] = CLOSURE_SUPPLEMENT
        result["note"] += "；另登记主动补充（原作答判定 %s），只升级事实包，不发第二轮" % answer_reason
    else:
        result["closure_reason"] = answer_reason
    return result


# ---------------------------------------------------------------- CLI
def _runner(payload):
    if not isinstance(payload, dict):
        raise InputError("NOT_AN_OBJECT", "顶层必须是 JSON 对象")
    if "answer_text" in payload:
        return close_fact_round(
            payload.get("answer_text"),
            unanswered_items=payload.get("unanswered_items"),
            answered_items=payload.get("answered_items"),
            sent_rounds=payload.get("sent_rounds", 1),
            max_rounds=payload.get("max_rounds", 1),
            supplement_text=payload.get("supplement_text"),
        )
    packet = payload.get("packet")
    if isinstance(packet, dict):
        return review_packet(packet)
    return review_packet(payload)


def _parser():
    parser = argparse.ArgumentParser(
        prog="python -m cad_agent_showcase.governance.neutral",
        description="公共事实包中性审查（packet）或事实轮关闭判定（answer_text）")
    parser.add_argument("path", help="含 packet 或 answer_text 的 JSON 文件")
    return parser


def cli(argv=None):
    args = _parser().parse_args(argv)
    from .envelope import run_cli
    return run_cli("neutral", _runner, args)


if __name__ == "__main__":
    import sys
    sys.exit(cli(sys.argv[1:]))
