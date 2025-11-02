"""Consent Lab: a minimal, URL-shareable playground to think about consent.

No scores or win/lose. It records small steps (clarify, agree, later),
surfaces inherent threats via prompts, and lets participants compare
"small" vs "big" consent scenarios without domain baggage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from ..deps import db_session
from ..domain.models import (
    ActType,
    ActorType,
    SessionRecord,
    UnderstandingEventCreate,
)
from ..domain.schemas import MetricsSnapshotOut, zone_label, zone_message
from ..services.ledger import LedgerService
from ..services.telemetry import TelemetryService


router = APIRouter()


def _templates() -> Jinja2Templates:
    return Jinja2Templates(directory="concordia/app/templates")

# Persist toggle: default OFF for Consent Lab demo
PERSIST = os.getenv("CONSENT_LAB_PERSIST", "0").lower() not in ("0", "false", "")


SCENARIOS: Dict[str, dict] = {
    # ① グループで撮った写真をインスタに載せていいか
    "photo_instagram": {
        "id": "photo_instagram",
        "title": "グループ写真をInstagramに投稿",
        "context": "みんなで撮った写真をインスタに載せたい。写り込みや将来の再共有も含めて、どうする？",
        "tags": ["小さな合意", "公開範囲", "本人以外の影響"],
    },
    # ② 不動産の契約を行う
    "real_estate_contract": {
        "id": "real_estate_contract",
        "title": "不動産の契約を行う",
        "context": "高額で長期の契約。連帯保証や与信、将来の解約条件も含めて、今この場で決める？",
        "tags": ["大きな合意", "高額", "撤回困難", "関係者多数"],
    },
    # ③ 結婚をする
    "marriage": {
        "id": "marriage",
        "title": "結婚する",
        "context": "人生の大きな決断。家族・法律・生活の変化、時間をかけた合意形成が必要？",
        "tags": ["大きな合意", "長期", "不可逆性", "関係者多数"],
    },
}

# Drag & Drop targets (inherent threats) and cards (security techniques)
THREATS: Dict[str, dict] = {
    "authority": {
        "id": "authority", "label": "立場の圧",
        "desc": "目上や専門家の前で断りづらい",
        "explain": "立場や専門性の差が“断りづらさ”を生み、同意/不同意/保留の出し方が不公平になります。評価や関係悪化への不安が本音の表明を妨げます。"
    },
    "time": {
        "id": "time", "label": "時間の圧",
        "desc": "急かされて決めたくなる",
        "explain": "“今だけ”や締切により熟慮の余地が減り、損失回避で拙速な選択をしがちになります。"
    },
    "surveillance": {
        "id": "surveillance", "label": "拡散リスク",
        "desc": "勝手に広まったり共有されそう",
        "explain": "その場や後日、内容が記録・共有・再利用されて広まってしまう懸念。切り取りや再投稿を不安に感じると、本音の表明が難しくなります。"
    },
    "irreversibility": {
        "id": "irreversibility", "label": "戻しづらさ",
        "desc": "一度決めると戻しにくい",
        "explain": "投稿/契約などはコピーや再共有で完全な取り消しが難しく、決定を重くします。段階化が必要です。"
    },
    "asymmetry": {
        "id": "asymmetry", "label": "わかりにくさ",
        "desc": "用語や条件がむずかしい",
        "explain": "情報・語彙・手続の差で、分からないまま同意してしまうリスクが生じます。" 
    },
}

CARDS: Dict[str, dict] = {
    "hash_chain": {"id": "hash_chain", "label": "改ざん防止の鎖", "effect": "後からの書き換え不安を低減", "explain": "出来事を連鎖で固定し、後から改ざんされないことを示します。『言った/言わない』の不安を下げます。"},
    "timestamp": {"id": "timestamp", "label": "外部の時刻で証明", "effect": "時刻・順序を裏付け", "explain": "外部の時刻源で“いつ起きたか”を裏付けます。順序に関する疑義を抑えます。"},
    "two_party_sig": {"id": "two_party_sig", "label": "二人で署名", "effect": "同意の強要を避ける痕跡", "explain": "双方の意思痕跡を同時に残し、一方的な同意取得や押し付けを避けます。"},
    "scoped_token": {"id": "scoped_token", "label": "使い道をしぼる", "effect": "範囲・期限・対象を限定", "explain": "“何のために・いつまで・何を”という条件を付け、過剰な開示を避けます。"},
    "anon_clarify": {"id": "anon_clarify", "label": "匿名で質問", "effect": "質問の心理的障壁を下げる", "explain": "質問を匿名/非同期にして、“愚問恐怖”を外します。"},
    "forget": {"id": "forget", "label": "鍵を捨てる", "effect": "将来の削除を技術で担保", "explain": "暗号鍵の破棄で実質的な削除を担保し、将来の不安を和らげます。"},
    "selective_visibility": {"id": "selective_visibility", "label": "見せ先をしぼる", "effect": "誰に何を見せるか制御", "explain": "閲覧範囲を細かく選び、“拡散リスク”を下げます。"},
    # 追加の“技術っぽい”カード
    "signed_link": {"id": "signed_link", "label": "署名付き共有リンク", "effect": "受け取り手を限定", "explain": "署名/有効期限/回数制限を付けたリンクで共有。リンク自体が本人宛であることを示し、横流しを抑えます。"},
    "view_once": {"id": "view_once", "label": "ワンタイム表示", "effect": "1回だけ見える", "explain": "一度だけ開ける閲覧形式。再共有やスクリーンショットの抑止に効きます（完全ではありません）。"},
    "watermark": {"id": "watermark", "label": "透かし/オーナー刻印", "effect": "リシェア検出", "explain": "画像に不可視/可視の透かしや宛先IDを埋め込み、拡散時の追跡と抑止に使います。"},
    "face_blur": {"id": "face_blur", "label": "自動ぼかし（顔/位置）", "effect": "識別性を下げる", "explain": "顔や位置情報の自動マスキングで、個人が特定されにくい状態にします。"},
    "consent_receipt": {"id": "consent_receipt", "label": "合意レシート", "effect": "内容固定の控えを発行", "explain": "改ざん防止のレシートをその場で発行。後から『そんなはずでは』を避けます。"},
    "diff_highlight": {"id": "diff_highlight", "label": "差分ハイライト", "effect": "変更点だけ強調", "explain": "契約/条件の更新時に変更箇所だけ強調し、理解の取りこぼしを減らします。"},
    "escrow_sig": {"id": "escrow_sig", "label": "二段階署名", "effect": "すぐ確定しない", "explain": "相手→自分の二段階。自分が押すまで確定しない“技術的ブレーキ”を仕込みます。"},
    "expiry_policy": {"id": "expiry_policy", "label": "期限付き公開", "effect": "自動で消える", "explain": "24時間などの自動失効を強制。残り続ける不安を減らします。"},
}

# Storylines: minimal, linear steps per scenario for solo demo
STORYLINES: Dict[str, list[dict]] = {
    # 各ステップに、その場で考えたい「内在的脅威」を限定提示
    "photo_instagram": [
        {"narration": "友人: インスタにこのグループ写真、載せてもいい？", "hint": "友だちの友だちにも広がるかも", "threats": ["surveillance"], "pair": {"threat": "surveillance", "card": "face_blur"}, "pair_reason": "写っている人が特定されにくいように自動ぼかしをかける"},
        {"narration": "友人: 公開範囲やタグ付けはどうしようか。", "hint": "設定しだいで見られる相手が変わる", "threats": ["surveillance"], "pair": {"threat": "surveillance", "card": "watermark"}, "pair_reason": "透かし/宛先IDを入れて、リシェア時に追跡しやすくする"},
        {"narration": "友人: ストーリーで上げとくわ。どう？", "hint": "24時間で消えるから残りにくい", "threats": ["irreversibility"], "pair": {"threat": "irreversibility", "card": "expiry_policy"}, "pair_reason": "自動で消える期限付きの公開にして、残り続けないようにする"}
    ],
    "real_estate_contract": [
        {"narration": "担当者: 今決めてもらえると特典があります。", "hint": "“今だけ”は急がせやすい", "threats": ["time"], "pair": {"threat": "time", "card": "escrow_sig"}, "pair_reason": "二段階署名にして“今すぐ確定しない”技術的ブレーキを入れる"},
        {"narration": "担当者: 条件は…（違約金/更新/保証など）。", "hint": "専門用語が多くて分かりにくい", "threats": ["asymmetry"], "pair": {"threat": "asymmetry", "card": "diff_highlight"}, "pair_reason": "変更箇所をハイライトして、理解の取りこぼしを減らす"},
        {"narration": "担当者: 契約は長期で、途中解約には制約がある。", "hint": "決めた後は戻しづらい", "threats": ["irreversibility"], "pair": {"threat": "irreversibility", "card": "consent_receipt"}, "pair_reason": "改ざん防止の“合意レシート”で、認識のズレを後に残さない"},
        {"narration": "担当者: では検討の時間を取りましょう。", "threats": []},
    ],
    "marriage": [
        {"narration": "相手: 結婚についてどう考えている？", "hint": "決めると生活が大きく変わり、戻しづらい", "threats": ["irreversibility"], "pair": {"threat": "irreversibility", "card": "escrow_sig"}, "pair_reason": "二段階署名にして“一度押したら終わり”にならないようにする"},
        {"narration": "相手: 住む場所・仕事・家族との向き合いは？", "hint": "話題が多くて、理解が追いつきにくい", "threats": ["asymmetry"], "pair": {"threat": "asymmetry", "card": "anon_clarify"}, "pair_reason": "質問をためて非同期で整理・回答する"},
        {"narration": "相手: 今日はここまでにしよう。時間を置いて考えよう。", "threats": ["irreversibility"], "pair": {"threat": "irreversibility", "card": "consent_receipt"}, "pair_reason": "今日の認識を“合意レシート”に固定して、次回の土台にする"},
    ],
}


@router.get("/lab", response_class=HTMLResponse)
def lab_index(request: Request):
    return _templates().TemplateResponse(
        "lab_index.html", {"request": request, "scenarios": list(SCENARIOS.values())}
    )




@router.post("/lab/story/new")
def lab_new_story(
    scenario_id: str = Form(...),
    initiator_id: str = Form("guide"),
    responder_id: str = Form("user"),
    session: Session = Depends(db_session),
):
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=400, detail="Unknown scenario")
    sid = f"story-{uuid4().hex[:8]}"
    if PERSIST:
        record = SessionRecord(
            id=sid,
            doctor_id=initiator_id,
            title=f"Consent Story: {SCENARIOS[scenario_id]['title']}",
            artifact_hash=SCENARIOS[scenario_id]["id"],
        )
        session.add(record)
        session.flush(); session.refresh(record)
        # first PRESENT
        LedgerService(session).append(
            UnderstandingEventCreate(
                session_id=sid,
                actor_id=initiator_id,
                actor_type=ActorType.DOCTOR,
                act_type=ActType.PRESENT,
                payload={"scenario": scenario_id, "context": SCENARIOS[scenario_id]["context"]},
                artifact_hash=SCENARIOS[scenario_id]["id"],
            )
        )
    return RedirectResponse(url=f"/lab/story/{sid}?scenario={scenario_id}&i=0", status_code=303)


@router.get("/lab/story/{session_id}", response_class=HTMLResponse)
def lab_story(
    request: Request,
    session_id: str,
    scenario: str,
    i: int = 0,
    initiator: str = "guide",
    responder: str = "user",
    session: Session = Depends(db_session),
):
    if scenario not in STORYLINES:
        raise HTTPException(status_code=404, detail="Story not found")
    steps = STORYLINES[scenario]
    total = len(steps)
    idx = max(0, min(i, total))
    current = steps[idx] if idx < total else {"narration": "完了しました。タイムラインを確認できます。", "threats": []}
    # シナリオに即した内在的脅威のみを段階表示
    visible_ids = current.get("threats", [])
    filtered_threats = [t for t in THREATS.values() if t["id"] in visible_ids]
    # おすすめカード（1対1）
    pair = current.get("pair") or {}
    pair_card_id = pair.get("card")
    pair_threat_id = pair.get("threat")
    pair_reason = current.get("pair_reason")
    if pair_card_id:
        filtered_cards = [c for c in CARDS.values() if c["id"] == pair_card_id]
    else:
        filtered_cards = []  # その場にカードがない場合は提示しない
    return _templates().TemplateResponse(
        "lab_story.html",
        {
            "request": request,
            "session_id": session_id,
            "scenario_id": scenario,
            "title": SCENARIOS[scenario]["title"],
            "context": SCENARIOS[scenario]["context"],
            "step_index": idx,
            "step_total": total,
            "narration": current.get("narration", ""),
            "hint": current.get("hint", ""),
            "initiator": initiator,
            "responder": responder,
            "threats": filtered_threats,
            "cards": filtered_cards,
            "pair_card_id": pair_card_id,
            "pair_threat_id": pair_threat_id,
            "pair_reason": pair_reason,
            "persist": PERSIST,
        },
    )


@router.post("/lab/story/{session_id}/advance")
def lab_story_advance(
    session_id: str,
    scenario: str = Form(...),
    i: int = Form(...),
    initiator: str = Form("guide"),
    responder: str = Form("user"),
    session: Session = Depends(db_session),
):
    if scenario not in STORYLINES:
        raise HTTPException(status_code=404, detail="Story not found")
    steps = STORYLINES[scenario]
    if i < 0 or i >= len(steps):
        return RedirectResponse(url=f"/lab/story/{session_id}?scenario={scenario}&i={len(steps)}&initiator={initiator}&responder={responder}", status_code=303)

    step = steps[i]
    if PERSIST:
        # apply event
        ev = step.get("event")
        if ev:
            role = ev.get("role", "responder")
            actor_id = responder if role == "responder" else initiator
            act_map = {
                "clarify": ActType.CLARIFY_REQUEST,
                "later": ActType.ASK_LATER,
                "agree": ActType.AGREE,
                "decline": ActType.PENDING,
                "revisit": ActType.RE_VIEW,
                "re_explain": ActType.RE_EXPLAIN,
                "mitigate_remove": ActType.MITIGATE_REMOVE,
            }
            ledger_event = UnderstandingEventCreate(
                session_id=session_id,
                actor_id=actor_id,
                actor_type=ActorType.PATIENT if role == "responder" else ActorType.DOCTOR,
                act_type=act_map[ev["act"]],
                payload={"note": ev.get("note", "")} if ev.get("note") else {},
            )
            LedgerService(session).append(ledger_event)
        # apply mitigation
        mit = step.get("mitigate")
        if mit:
            LedgerService(session).append(
                UnderstandingEventCreate(
                    session_id=session_id,
                    actor_id=responder,
                    actor_type=ActorType.PATIENT,
                    act_type=ActType.MITIGATE,
                    payload={"card": mit.get("card"), "threat": mit.get("threat")},
                )
            )

    return RedirectResponse(url=f"/lab/story/{session_id}?scenario={scenario}&i={i+1}&initiator={initiator}&responder={responder}", status_code=303)


@router.get("/lab/{session_id}/play", response_class=HTMLResponse)
def lab_play(request: Request, session_id: str, role: str, user: str, session: Session = Depends(db_session)):
    record = session.get(SessionRecord, session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    # get last snapshot for scoreboard
    metrics = TelemetryService(session).snapshot_for_session(session_id)
    metrics_out = MetricsSnapshotOut(**metrics.model_dump())
    metrics_out.zone_label = zone_label(metrics_out.comfort_zone)
    metrics_out.zone_message = zone_message(metrics_out.comfort_zone)

    return _templates().TemplateResponse(
        "lab_play.html",
        {
            "request": request,
            "session_id": session_id,
            "title": record.title,
            "artifact_hash": record.artifact_hash,
            "role": role,
            "user": user,
            "share_url": f"/lab/{session_id}/play?role=responder&user={user}",
            "metrics": metrics_out,
            "threats": list(THREATS.values()),
            "cards": list(CARDS.values()),
        },
    )


@router.post("/lab/{session_id}/act")
def lab_act(
    session_id: str,
    actor_id: str,
    actor_role: str,
    act: str,
    note: Optional[str] = None,
    session: Session = Depends(db_session),
):
    role = ActorType.DOCTOR if actor_role == "initiator" or actor_role == "doctor" else ActorType.PATIENT
    mapping = {
        "clarify": ActType.CLARIFY_REQUEST,
        "later": ActType.ASK_LATER,
        "agree": ActType.AGREE,
        "decline": ActType.PENDING,
        "revisit": ActType.RE_VIEW,
        "re_explain": ActType.RE_EXPLAIN,
        "mitigate": ActType.MITIGATE,
    }
    act_type = mapping.get(act)
    if not act_type:
        raise HTTPException(status_code=400, detail="Unknown act")
    payload = {"note": note} if note else {}

    if PERSIST:
        event = UnderstandingEventCreate(
            session_id=session_id,
            actor_id=actor_id,
            actor_type=role,
            act_type=act_type,
            payload=payload,
        )
        saved = LedgerService(session).append(event)
        TelemetryService(session).snapshot_for_session(session_id)
        return {"ok": True, "event_id": saved.id}
    else:
        return {"ok": True}
