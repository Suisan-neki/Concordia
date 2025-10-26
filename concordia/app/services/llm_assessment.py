"""LLM-based comprehension quality assessment service."""
from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Optional

import google.generativeai as genai
from sqlmodel import Session, select

from ..domain.models import (
    ComprehensionAssessment,
    ComprehensionQuality,
    UnderstandingEvent,
    ActorType,
    ActType,
)


class LLMAssessmentService:
    """Assess comprehension quality using LLM-based analysis."""

    def __init__(self, session: Session) -> None:
        self.session = session
        # Gemini API を初期化
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')

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
            confidence_score=result["confidence"],
            reasoning=result["reasoning"],
            concerns=result["concerns"],
            metadata=result["metadata"],
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

JSON形式で返答してください:
{{
  "quality": "high|moderate|low",
  "confidence": 0.0-1.0,
  "reasoning": "判定理由",
  "concerns": "懸念点（なければ空文字列）"
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
                "confidence": float(result.get("confidence", 0.5)),
                "reasoning": result.get("reasoning", ""),
                "concerns": result.get("concerns", ""),
                "metadata": {
                    "model": "gemini-pro",
                    "api_provider": "google",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }
            
        except Exception as e:
            # エラー時はモック実装にフォールバック
            print(f"LLM API エラー: {e}")
            return self._mock_assessment(conversation)

    def _mock_assessment(self, conversation: str) -> dict:
        """モック実装: 会話のターン数で判定"""
        lines = conversation.count("\n")
        
        if lines > 10:
            quality = ComprehensionQuality.HIGH
            confidence = 0.8
            reasoning = f"会話に{lines}ターンあり、双方向性が十分に見られます。"
            concerns = ""
        elif lines > 5:
            quality = ComprehensionQuality.MODERATE
            confidence = 0.6
            reasoning = f"会話に{lines}ターンあり、やや不足があります。"
            concerns = "患者の反応が少ない可能性があります。"
        else:
            quality = ComprehensionQuality.LOW
            confidence = 0.5
            reasoning = f"会話が短く（{lines}ターン）、理解が不十分な可能性があります。"
            concerns = "構造的な再説明が必要です。"
        
        return {
            "quality": quality,
            "confidence": confidence,
            "reasoning": reasoning,
            "concerns": concerns,
            "metadata": {
                "model": "mock-v1",
                "prompt_version": "1.0",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
