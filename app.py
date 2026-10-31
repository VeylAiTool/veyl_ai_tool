from flask import Flask
from config import Config
from models.models import db
from flask_login import LoginManager
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
from routes.auth import auth_bp
from routes.chat import chat_bp
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
@login_manager.user_loader
def load_user(user_id):
    from models.models import User
    return User.query.get(int(user_id))
with app.app_context():
    db.create_all()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
