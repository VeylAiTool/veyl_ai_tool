from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models.models import db, Conversation, Message
import requests
import time
import os

chat_bp = Blueprint('chat', __name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"

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

def call_groq_with_retry(payload, headers, max_retries=6):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                GROQ_API_URL,
                headers=headers,
                json=payload,
                timeout=120
            )
            if response.status_code == 429:
                retry_after = int(response.headers.get('retry-after', 5))
                time.sleep(retry_after * (2 ** attempt))
                continue
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get('retry-after', 5))
                time.sleep(retry_after * (2 ** attempt))
                continue
            raise e
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)
    return "عذراً، الخادم مشغول جداً حالياً. يرجى المحاولة بعد بضع دقائق."

@chat_bp.route('/api/chat/<int:conv_id>', methods=['POST'])
@login_required
def send_message(conv_id):
    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
        
    conv = Conversation.query.get_or_404(conv_id)
    if conv.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    # 1. حفظ رسالة المستخدم
    msg = Message(conversation_id=conv.id, role='user', content=user_message)
    db.session.add(msg)
    if conv.title == "New Chat" and len(user_message) > 0:
        conv.title = user_message[:30]
    db.session.commit()

    # 2. جلب تاريخ المحادثة (آخر 10 رسائل)
    history = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.asc()).all()
    # أخذ آخر 10 رسائل فقط لتوفير الرموز
    recent_history = history[-10:] if len(history) > 10 else history

    messages_payload = [
        {"role": "system", "content": "You are Veyl, a helpful AI assistant. Reply in the same language as the user."}
    ]
    for h in recent_history:
        messages_payload.append({"role": h.role, "content": h.content})

    headers = {
        "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY', '')}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": GROQ_MODEL,
        "messages": messages_payload,
        "temperature": 0.7,
        "max_completion_tokens": 2048
    }
    
    try:
        bot_reply = call_groq_with_retry(payload, headers)
    except Exception as e:
        bot_reply = f"Error: {str(e)}"

    # 3. حفظ رد البوت
    bot_msg = Message(conversation_id=conv.id, role='assistant', content=bot_reply)
    db.session.add(bot_msg)
    db.session.commit()

    return jsonify({"reply": bot_reply})
