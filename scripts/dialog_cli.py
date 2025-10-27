#!/usr/bin/env python3
"""Interactive CLI to simulate talker-listener sessions."""
from __future__ import annotations

import argparse
import os
import random

import google.generativeai as genai
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, select

from concordia.app.domain.models import ActType, ActorType, UnderstandingEvent
from concordia.app.infra.db import ensure_acttype_enum_values
from concordia.app.services.telemetry import TelemetryService

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"

PROMPTS = [
    f"{BOLD}{CYAN}💭 話し手>{RESET} ",
    f"{BOLD}{GREEN}👂 聞き手>{RESET} ",
]


def init_gemini() -> genai.GenerativeModel | None:
    """Initialize Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(f"{YELLOW}⚠️  GEMINI_API_KEY が設定されていません。フォールバックモードで動作します。{RESET}")
        return None
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        # Test if API key works
        test_response = model.generate_content("test")
        print(f"{GREEN}✓ Gemini API に接続しました{RESET}")
        return model
    except Exception as e:
        print(f"{YELLOW}⚠️  Gemini API の初期化に失敗: {e}{RESET}")
        print(f"{YELLOW}フォールバックモードで動作します{RESET}")
        return None


def generate_theme(llm: genai.GenerativeModel | None) -> str:
    """Generate a conversation theme using LLM."""
    themes = [
        "今日の夕食をどこで食べるか",
        "週末どこに行くか",
        "次に見る映画を何にするか",
        "今度の旅行の行き先",
        "ディナーのお店をどこにするか",
    ]
    
    if not llm:
        return random.choice(themes)
    
    prompt = """二人が一緒に決める必要がある、具体的な選択肢があるテーマを提案してください。
例: 
- 今日の夕食をどこで食べるか
- 週末どこに行くか
- 次に見る映画を何にするか
- 今度の旅行の行き先

※重要：2つ以上の選択肢があり、二人で合意できる具体的な内容にしてください。
回答は引用符なしでシンプルに1行だけ。"""
    try:
        response = llm.generate_content(prompt)
        theme = response.text.strip()
        # Remove quotes and other artifacts
        theme = theme.replace('"', '').replace("'", "").replace('「', '').replace('」', '').strip()
        # Take first line only
        theme = theme.split('\n')[0].strip()
        
        # If theme is too generic or empty, use fallback
        if not theme or theme == "今日の話題" or len(theme) < 10:
            return random.choice(themes)
        return theme
    except Exception:
        return random.choice(themes)


def generate_listener_response(llm: genai.GenerativeModel | None, speaker_text: str, history: list, theme: str = "") -> str:
    """Generate listener response using LLM."""
    # Smart fallback without LLM
    def get_fallback_response():
        if "犬" in theme or "猫" in theme:
            responses = [
                "犬と猫なら、私は猫派かな。散歩もいらないし、自由な感じが好き。",
                "うーん、犬派だな。一緒に散歩に行けるのが楽しそう。",
                "猫かな。お世話が楽そうだし、のんびりしてそう。"
            ]
        elif "映画" in theme:
            responses = [
                "映画なら、アクション映画が好きかな。",
                "最近コメディ映画を見たいな。笑いたいから。",
                "サスペンス映画が好き。ドキドキするのがいいの。"
            ]
        elif "旅行" in theme or "行き先" in theme:
            responses = [
                "旅行なら、温泉に行きたいな。のんびりしたい。",
                "海外旅行がしたい。異文化を感じたい。",
                "山に登りたい。自然の中でリフレッシュしたい。"
            ]
        elif "夕食" in theme or "食べる" in theme:
            responses = [
                "食事ならイタリアンが食べたいな。",
                "今日は和食が食べたい。",
                "中華料理がいい。味が濃くて好き。"
            ]
        else:
            responses = [
                "うーん、それは難しい選択だね。",
                "そうか、なるほど。もう少し考えたいな。",
                "その選択は面白いね。他にも考えたい。"
            ]
        return random.choice(responses)
    
    if not llm:
        return get_fallback_response()
    
    # Build context from recent history with proper pairing
    # history contains alternating speaker/listener in order
    context_lines = []
    for i in range(len(history)):
        if i % 2 == 0:  # Speaker turns
            context_lines.append(f"話し手: {history[i]['text']}")
        else:  # Listener turns
            context_lines.append(f"聞き手: {history[i]['text']}")
    context = "\n".join(context_lines[-6:])  # Last 3 exchanges (6 turns)
    
    # Add theme to context if available
    theme_context = f"\n【テーマ】{theme}\n" if theme else ""
    
    prompt = f"""あなたは会話の聞き手役です。相手と話し合って、{theme}について合意を目指しています。
{theme_context}
【会話の流れ】
{context}

【相手の発言】
{speaker_text}

【重要】あなたの返答ルール：
1. 相手の発言を理解する（何を言っているかを把握する）
2. 自分なりの意見や考えを具体的に述べる
3. 質問されたら明確に答える（例：「どっち？」→「猫。理由は...」）
4. 合意に近づくように前向きに対話する
5. 2-3文で簡潔に、自然な口調で

※重要：「難しい質問ですね」や「考えさせてください」は使わない。必ず具体的な意見を述べる。

聞き手の返答: """
    
    try:
        response = llm.generate_content(prompt)
        reply = response.text.strip()
        
        # Check if response is empty or error
        if not reply or len(reply) < 5:
            raise ValueError("Empty or too short response")
        
        # Remove artifacts
        for prefix in ["聞き手:", "聞き手の返答:", "> "]:
            if reply.startswith(prefix):
                reply = reply[len(prefix):].strip()
        
        # Limit length
        if len(reply) > 120:
            reply = reply[:120] + "..."
        
        # Clean up
        reply = reply.strip().rstrip('...').strip()
        
        # Only fallback if truly generic
        generic_phrases = ["そうなんだね", "なるほど", "そうか", "へえ"]
        if any(phrase in reply for phrase in generic_phrases) and len(reply) < 10:
            # Force a specific response based on theme
            if "犬" in theme or "猫" in theme:
                return "犬と猫なら私は猫派かな。散歩もいらないし、自由な感じが好き。"
            elif "夕食" in theme:
                return "今日はカレーが食べたいな。あなたは何が食べたい？"
            else:
                return "そうだね、良い考えだと思う。具体的にはどうする？"
        
        return reply if reply else "そうだね、それについてもう少し考えよう。"
        
    except Exception as e:
        # Fallback when LLM fails (quota, error, etc.)
        return get_fallback_response()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate a dialog session")
    parser.add_argument("session_id")
    parser.add_argument("--doctor-id", default="doc-cli")
    parser.add_argument("--patient-id", default="pat-cli")
    parser.add_argument("--database-url",
                        default="postgresql+psycopg://concordia:concordia@db:5432/concordia")
    return parser.parse_args()


def record_event(db: Session, session_id: str, actor_id: str, actor_type: ActorType,
                 act_type: ActType, payload: dict):
    event = UnderstandingEvent(
        session_id=session_id,
        actor_id=actor_id,
        actor_type=actor_type,
        act_type=act_type,
        payload=payload,
    )
    db.add(event)
    db.flush()
    db.refresh(event)
    return event


def phase_comment(summary: dict) -> str:
    counts = summary.get("zone_counts", {})
    if counts.get("focus", 0) > 0:
        return "集中して理解しようとしてくれています。要点を小分けにすると安心感が戻るかもしれません。"
    if counts.get("observe", 0) > 0:
        return "様子見モードです。質問のきっかけをもう一度提示してみましょう。"
    return "穏やかに対話が続いています。この調子で進めましょう。"


def format_comfort_zone(zone_str: str) -> str:
    """Convert comfort zone enum to user-friendly message."""
    zone_map = {
        "ComfortZone.CALM": f"{GREEN}😌 穏やか{RESET}",
        "ComfortZone.OBSERVE": f"{YELLOW}👀 様子見{RESET}",
        "ComfortZone.FOCUS": f"{MAGENTA}🎯 集中{RESET}",
    }
    return zone_map.get(zone_str, zone_str)


def print_header(text: str) -> None:
    """Print a styled header with emoji."""
    emoji_map = {
        "セッション開始": "🚀",
        "セッション終了": "🏁",
    }
    emoji = emoji_map.get(text, "📋")
    
    print(f"\n{BOLD}{BLUE}{'═'*50}{RESET}")
    print(f"{BOLD}{BLUE}{emoji}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{'═'*50}{RESET}\n")


def print_thinking_dots() -> None:
    """Print animated thinking dots."""
    import time
    for i in range(3):
        dots = "." * (i + 1) + " " * (2 - i)
        print(f"\r{YELLOW}💭 考え中{dots}{RESET}", end="", flush=True)
        time.sleep(0.3)
    print("\r" + " " * 20 + "\r", end="")


def print_summary(session_id: str, db: Session) -> None:
    """Print session summary."""
    print_header(f"セッション終了: {session_id}")
    
    snapshot = TelemetryService(db).snapshot_for_session(session_id)
    print(f"{BOLD}{BLUE}📊 会話の状況:{RESET} {format_comfort_zone(str(snapshot.comfort_zone))}\n")
    
    # Count agreement events
    events = db.exec(
        select(UnderstandingEvent)
        .where(UnderstandingEvent.session_id == session_id)
        .where(UnderstandingEvent.act_type == ActType.AGREE)
    ).all()
    
    if events:
        print(f"{BOLD}{GREEN}🎉 素晴らしい！合意に到達しました！{RESET}\n")
        print(f"{GREEN}{'='*50}{RESET}")
        print(f"{GREEN}　双方が納得できる内容で合意できました{RESET}")
        print(f"{GREEN}{'='*50}{RESET}\n")
    else:
        print(f"{YELLOW}💭 今回は合意には至りませんでした{RESET}")
        print(f"{CYAN}ゼロプレッシャーの対話では、合意に至らないことも貴重な体験です{RESET}")
        print(f"{CYAN}お互いの考えを尊重しながら、もう一度時間をかけて話し合う機会を持てると良いですね{RESET}\n")
        
        # Count total exchanges
        all_events = db.exec(
            select(UnderstandingEvent)
            .where(UnderstandingEvent.session_id == session_id)
        ).all()
        exchange_count = len(all_events) // 2
        print(f"{CYAN}📈 会話数: {exchange_count} 往復{RESET}\n")


def main() -> int:
    args = parse_args()
    engine = create_engine(args.database_url, future=True)
    ensure_acttype_enum_values(engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False)
    
    # Initialize LLM
    llm = init_gemini()

    with SessionLocal() as db:
        # Generate and display theme
        theme = generate_theme(llm)
        print_header(f"セッション開始: {args.session_id}")
        print(f"{BOLD}{MAGENTA}🎯 今回のテーマ:{RESET} {CYAN}{theme}{RESET}")
        print(f"{BOLD}{GREEN}💡 ヒント:{RESET} 空行を入力すると終了します")
        print(f"{YELLOW}🤖 聞き手は AI が担当します{RESET}\n")
        
        history = []
        
        while True:
            utter = input(PROMPTS[0])
            if not utter:
                break
            
            record_event(db, args.session_id, args.doctor_id, ActorType.DOCTOR,
                         ActType.PRESENT, {"text": utter})
            history.append({"text": utter})
            
            # Generate listener response using LLM
            listener_reply = generate_listener_response(llm, utter, history, theme)
            print(f"{PROMPTS[1]}{listener_reply}")
            
            # Determine act type based on response content
            act_type = ActType.SIGNAL_ACK  # Default
            reply_lower = listener_reply.lower()
            if any(word in reply_lower for word in ["？", "?", "なに", "どう", "なぜ", "なぜ", "教えて"]):
                act_type = ActType.SIGNAL_QUESTION
            elif any(word in reply_lower for word in ["いいね", "面白い", "おもしろ", "すごい"]):
                act_type = ActType.SIGNAL_PRAISE
            
            record_event(db, args.session_id, args.patient_id, ActorType.PATIENT,
                         act_type, {"text": listener_reply})
            history.append({"text": listener_reply})
            db.commit()

        print_summary(args.session_id, db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
