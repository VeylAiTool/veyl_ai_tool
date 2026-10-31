from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models.models import db, Conversation, Message
from config import Config
import requests
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
    headers = {"Authorization": f"Bearer {Config.GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "openai/gpt-oss-120b", "messages": [{"role": "system", "content": "You are Veyl, a helpful AI assistant."}, {"role": "user", "content": user_message}], "temperature": 0.7}
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        bot_reply = response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        bot_reply = f"Error: {str(e)}"
    bot_msg = Message(conversation_id=conv.id, role='assistant', content=bot_reply)
    db.session.add(bot_msg)
    db.session.commit()
    return jsonify({"reply": bot_reply})
