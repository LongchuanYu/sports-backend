import json
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

db = SQLAlchemy()

def create_app():

    app = Flask(__name__)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database/mydata.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

    CORS(app)
    db.init_app(app)

    from api import bp
    app.register_blueprint(bp)

    return app