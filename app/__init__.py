from flask import Flask
from flask_mysqldb import MySQL
from flask_login import LoginManager
from flask_mail import Mail
from flask_bcrypt import Bcrypt
from app.config import Config
import MySQLdb.cursors
from flask import render_template

mysql = MySQL()
login_manager = LoginManager()
mail = Mail()
bcrypt = Bcrypt()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

    mysql.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)

    login_manager.login_view = 'main.login'

    from app import models
    from app.routes import main
    app.register_blueprint(main)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    return app