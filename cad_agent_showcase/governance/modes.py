# -*- coding: utf-8 -*-
"""模式与工程就绪分离。

模式选择不等于工程就绪。本模块只给状态与标识，不生成 CAD，
不证明概念图或成品图已交付。
"""

import argparse
import sys

from .envelope import InputError

CONCEPT_WATERMARK = "概念方案—不得用于加工"
MODES = ("NO_DRAWING_CONCEPT", "DRAWING_TO_MANUFACTURING")


def concept_endpoint(candidate_version):
    """无图纸概念模式的终点是概念 CAD，强制水印。"""
    return {
        "mode": "NO_DRAWING_CONCEPT",
        "endpoint": "CONCEPT_CAD",
        "candidate_version": candidate_version,
        "watermark": CONCEPT_WATERMARK,
        "watermark_required": True,
        "manufacturing_symbols_allowed": False,
        "engineering_approval": False,
        "production_approved": False,
    }


def manufacturing_readiness(packet):
    """有图纸制造模式：缺材料或接口时 readiness=ENGINEERING_PENDING。

    不得输出“成品完成”或“可投产”。模式本身不抬就绪。
    """
    missing = []
    if not packet.get("material"):
        missing.append("material")
    if not packet.get("interfaces"):
        missing.append("interfaces")
    if not packet.get("process"):
        missing.append("process")
    if packet.get("interface_validated") is not True:
        missing.append("interface_validation")
    # Full manufacturing readiness is an explicit contract: a partial packet
    # must not become ready merely because material/interface labels exist.
    for name in ("loads", "datums", "tolerances", "capability"):
        if not packet.get(name):
            missing.append(name)
    capability = packet.get("capability")
    capability_problems = []
    if capability:
        if not isinstance(capability, dict):
            capability_problems.append("capability_not_object")
        else:
            if capability.get("supported") is not True:
                capability_problems.append("supported_not_true")
            if capability.get("engineering_mode") is not True:
                capability_problems.append("engineering_mode_not_true")
            if "can_enter_p2" in capability and capability["can_enter_p2"] is not True:
                capability_problems.append("can_enter_p2_not_true")
            if "status" in capability and capability["status"] not in ("SUPPORTED", "READY"):
                capability_problems.append("status_not_supported")
        if capability_problems and "capability" not in missing:
            missing.append("capability")
    pending = bool(missing)
    return {
        "mode": "DRAWING_TO_MANUFACTURING",
        "readiness": "ENGINEERING_PENDING" if pending else "READY_FOR_HUMAN_REVIEW",
        "pending_items": missing,
        "capability_problems": capability_problems,
        "readiness_evidence": "declared_input_only_not_backend_verification",
        "finished_claim": None,
        "production_claim": None,
        "engineering_approval": False,
        "production_approved": False,
        "synthetic_relabel_used": False,
    }


def transfer_parameter(parameter):
    """ASSUMED 尺寸经转加工保持原状态与 SHA，不升级为 USER_FACT。"""
    kept = dict(parameter)
    kept["evidence_status"] = parameter.get("original_evidence_status",
                                            parameter.get("evidence_status"))
    kept["source_sha256"] = parameter.get("source_sha256")
    if parameter.get("evidence_status") == "ASSUMED":
        kept["evidence_status"] = "ASSUMED"
    if kept["evidence_status"] != parameter.get("original_evidence_status",
                                                kept["evidence_status"]):
        raise ValueError("转加工不得改写来源状态")
    kept["upgraded_to_user_fact"] = False
    kept["numeric_eligibility"] = parameter.get("numeric_eligibility", "NOT_EVALUATED")
    return kept


def explicit_invocation(packet, invocation_event_ref):
    """转加工包存在但没有显式调用事件时，不自动调用。"""
    return {
        "packet_present": packet is not None,
        "invocation_event_ref": invocation_event_ref,
        "auto_invoked": False,
        "status": "INVOKED" if invocation_event_ref else "NOT_INVOKED",
        "invocation_executed": False,
        "execution_status": "NOT_EXECUTED",
        "status_semantics": "legacy status records an event reference only; it is not a backend execution receipt",
        "receipt_verified": False,
    }


def _runner(payload):
    """CLI 主体：按 mode 分流到概念终点或工程就绪。

    未识别 mode 是输入取值错误 → InputError（退出码 2），不是 SystemExit。
    """
    if not isinstance(payload, dict):
        raise InputError("NOT_AN_OBJECT", "顶层必须是 JSON 对象")
    mode = payload.get("mode")
    if mode == "NO_DRAWING_CONCEPT":
        return concept_endpoint(payload.get("candidate_version"))
    if mode == "DRAWING_TO_MANUFACTURING":
        return manufacturing_readiness(payload)
    raise InputError("MODE_UNKNOWN",
                     "mode 只能是 %s，收到 %r" % (",".join(MODES), mode),
                     "mode")


def _parser():
    parser = argparse.ArgumentParser(
        prog="python -m cad_agent_showcase.governance.modes",
        description="模式与工程就绪分离：mode=NO_DRAWING_CONCEPT 或 DRAWING_TO_MANUFACTURING")
    parser.add_argument("path", help="含 mode 的 JSON")
    return parser


def cli(argv=None):
    args = _parser().parse_args(argv)
    from .envelope import run_cli
    return run_cli("modes", _runner, args)


if __name__ == "__main__":
    sys.exit(cli())

