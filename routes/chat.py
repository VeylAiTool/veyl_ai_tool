from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models.models import db, Conversation, Message
import requests
import time
import os

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

def call_gemini_with_retry(payload, headers, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent",
                headers=headers,
                json=payload,
                timeout=120
            )
            if response.status_code == 429:
                retry_after = int(response.headers.get('retry-after', 10))
                wait_time = retry_after * (2 ** attempt)
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get('retry-after', 10))
                time.sleep(retry_after * (2 ** attempt))
                continue
            raise e
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)
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
        "Content-Type": "application/json",
        "x-goog-api-key": os.environ.get('GEMINI_API_KEY', '')
    }
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_message}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": "You are Veyl, a helpful AI assistant. Reply in the same language as the user."}]
        },
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192
        }
    }
    
    try:
        bot_reply = call_gemini_with_retry(payload, headers)
    except Exception as e:
        bot_reply = f"Error: {str(e)}"

    bot_msg = Message(conversation_id=conv.id, role='assistant', content=bot_reply)
    db.session.add(bot_msg)
    db.session.commit()

    return jsonify({"reply": bot_reply})
