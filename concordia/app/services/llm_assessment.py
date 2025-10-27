"""LLM-based comprehension quality assessment service."""
from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
import google.generativeai as genai
from sqlmodel import Session, select

from ..domain.models import (
    ComprehensionAssessment,
    ComprehensionQuality,
    UnderstandingEvent,
    ActorType,
    ActType,
)

# .env ファイルをロード
load_dotenv()


class LLMAssessmentService:
    """Assess comprehension quality using LLM-based analysis."""

    def __init__(self, session: Session) -> None:
        self.session = session
        # Gemini API を初期化
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def assess_session(self, session_id: str) -> ComprehensionAssessment:
        """Evaluate comprehension quality for a completed session."""
        events = self.session.exec(
            select(UnderstandingEvent)
            .where(UnderstandingEvent.session_id == session_id)
            .order_by(UnderstandingEvent.created_at)
        ).all()

        # 会話履歴を整形
        conversation = self._format_conversation(events)

        # LLM 評価
        result = self._call_llm_api(conversation)

        assessment = ComprehensionAssessment(
            session_id=session_id,
            overall_quality=result["quality"],
            agreement_readiness=result["agreement_readiness"],
            reasoning=result["reasoning"],
            suggestions=result["suggestions"],
            assessment_metadata=result["metadata"],
        )
        self.session.add(assessment)
        self.session.flush()
        self.session.refresh(assessment)
        return assessment

    def _format_conversation(self, events: list[UnderstandingEvent]) -> str:
        """Format events into a conversation transcript."""
        lines = []
        for event in events:
            role = "医師" if event.actor_type == ActorType.DOCTOR else "患者"
            act_label = {
                ActType.PRESENT.value: "説明",
                ActType.CLARIFY_REQUEST.value: "質問",
                ActType.ACK_SUMMARY.value: "要約確認",
                ActType.AGREE.value: "合意",
                ActType.PENDING.value: "保留",
                ActType.RE_EXPLAIN.value: "再説明",
            }.get(event.act_type.value, event.act_type.value)

            text = event.payload.get("text", "")
            lines.append(f"{role}: [{act_label}] {text}")

        return "\n".join(lines)

    def _call_llm_api(self, conversation: str) -> dict:
        """Call Gemini API to assess comprehension quality."""
        api_key = os.getenv("GEMINI_API_KEY")
        
        # API キーがない場合はモック実装にフォールバック
        if not api_key:
            return self._mock_assessment(conversation)
        
        try:
            prompt = f"""
医療診療における説明・理解の質を評価してください。

【会話履歴】
{conversation}

【評価基準】
- HIGH: 患者が十分に理解し、質問も活発で、双方向性が保たれている
- MODERATE: 一部不明点あり、再説明で改善可能
- LOW: 理解不足、構造的な再説明が必要

【重要な原則】
- 誰を責めるのではなく、対話の質を客観的に評価してください
- 「改善が必要」ではなく「さらに深い理解の機会がある」という肯定的な表現を使用してください
- 問題点を指摘するのではなく、より良い対話のためのヒントを提供してください

JSON形式で返答してください（すべて肯定的な表現で）:
{{
  "quality": "high|moderate|low",
  "agreement_readiness": "合意への準備度を肯定的な言葉で表現（例: '十分な情報交換ができている'）",
  "reasoning": "判定理由（肯定的な表現で）",
  "suggestions": "さらに良い対話のための提案（なければ空文字列）"
}}
"""
            
            response = self.model.generate_content(prompt)
            content = response.text.strip()
            
            # JSON をパース
            # Gemini はマークダウンのコードブロックを返す場合があるので処理
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            result = json.loads(content)
            
            # Enum に変換
            quality_map = {
                "high": ComprehensionQuality.HIGH,
                "moderate": ComprehensionQuality.MODERATE,
                "low": ComprehensionQuality.LOW,
            }
            
            return {
                "quality": quality_map.get(result["quality"], ComprehensionQuality.MODERATE),
                "agreement_readiness": result.get("agreement_readiness", "対話を通じて理解が深まっている"),
                "reasoning": result.get("reasoning", ""),
                "suggestions": result.get("suggestions", ""),
                "metadata": {
                    "model": "gemini-2.0-flash-exp",
                    "api_provider": "google",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }
            
        except Exception as e:
            # エラー時はモック実装にフォールバック
            print(f"LLM API エラー: {e}")
            return self._mock_assessment(conversation)

    def _mock_assessment(self, conversation: str) -> dict:
        """モック実装: 会話のターン数で判定（すべて肯定的な表現で）"""
        lines = conversation.count("\n")
        
        if lines > 10:
            quality = ComprehensionQuality.HIGH
            agreement_readiness = "十分な情報交換ができており、合意に近づいています"
            reasoning = f"会話に{lines}ターンあり、双方向性が十分に見られます。"
            suggestions = ""
        elif lines > 5:
            quality = ComprehensionQuality.MODERATE
            agreement_readiness = "さらなる質問の機会を活用することで、より深い理解につなげられます"
            reasoning = f"会話に{lines}ターンあり、対話の流れは良好です。"
            suggestions = "追加の質問があれば遠慮なくどうぞ。"
        else:
            quality = ComprehensionQuality.LOW
            agreement_readiness = "対話を続けることで、より良い理解につなげられます"
            reasoning = f"会話は{lines}ターン。双方向のやり取りを続けることで理解が深まります。"
            suggestions = "不明な点があれば、いつでも質問してください。"
        
        return {
            "quality": quality,
            "agreement_readiness": agreement_readiness,
            "reasoning": reasoning,
            "suggestions": suggestions,
            "metadata": {
                "model": "mock-v1",
                "prompt_version": "2.0-positive-only",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }