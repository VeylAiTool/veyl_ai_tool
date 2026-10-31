from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models.models import db, Conversation, Message
from config import Config
import requests
import time

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/')
@login_required
def index():
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.created_at.desc()).all()
    return render_template('chat.html', conversations=conversations)

@chat_bp.route('/tools')
@login_required
def tools():
    return render_template('tools.html')

@chat_bp.route('/api/new_chat', methods=['POST'])
@login_required
def new_chat():
    conv = Conversation(user_id=current_user.id, title="New Chat")
    db.session.add(conv)
    db.session.commit()
    return jsonify({"id": conv.id, "title": conv.title})

def call_groq_with_retry(payload, headers, max_retries=3):
    """دالة لإرسال الطلب مع إعادة المحاولة عند خطأ 429"""
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            # إذا كان الخطأ 429، انتظر وأعد المحاولة
            if response.status_code == 429:
                # قراءة الوقت المطلوب للانتظار من الترويسة (إن وجدت)
                retry_after = int(response.headers.get('retry-after', 5))
                wait_time = retry_after * (2 ** attempt)  # تأخير متزايد
                print(f"Rate limited. Waiting {wait_time} seconds... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get('retry-after', 5))
                wait_time = retry_after * (2 ** attempt)
                print(f"Rate limited. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            raise e
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)
    
    # إذا فشلت كل المحاولات
    return "عذراً، الخادم مشغول حالياً. يرجى المحاولة بعد قليل."

@chat_bp.route('/api/chat/<int:conv_id>', methods=['POST'])
@login_required
def send_message(conv_id):
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
        
    conv = Conversation.query.get_or_404(conv_id)
    if conv.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    msg = Message(conversation_id=conv.id, role='user', content=user_message)
    db.session.add(msg)
    
    if conv.title == "New Chat" and len(user_message) > 0:
        conv.title = user_message[:30]
    
    db.session.commit()

    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": "You are Veyl, a helpful AI assistant. Use web search when the user asks about current events, prices, or real-time information."},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_completion_tokens": 2048,
        "tools": [{"type": "browser_search"}],
        "tool_choice": "auto"
    }
    
    try:
        bot_reply = call_groq_with_retry(payload, headers)
    except Exception as e:
        bot_reply = f"Error: {str(e)}"

    bot_msg = Message(conversation_id=conv.id, role='assistant', content=bot_reply)
    db.session.add(bot_msg)
    db.session.commit()

    return jsonify({"reply": bot_reply})
