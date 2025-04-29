from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager 
import os
db = SQLAlchemy()
migrate = Migrate(db)

def create_app():     
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')   
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')    
    db.init_app(app)
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    with app.app_context():
        db.create_all()
        
    login_manager = LoginManager()
    login_manager.login_view = 'auth.Login'
    login_manager.init_app(app)
    from .models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    return app

