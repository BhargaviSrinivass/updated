# app.py
from flask import Flask, render_template
from flask_login import login_required 
from extensions import db, login_manager
from models import User, Problem, Submission, Video, Quiz, Question, Option, QuizAttempt, Post
from leaderboard import leaderboard as leaderboard_blueprint
from datetime import datetime
import os
import json

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secretkey123'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from auth import auth as auth_blueprint
    from problems import problems as problems_blueprint
    from explore import explore as explore_blueprint
    from quiz import quiz as quiz_blueprint
    from discuss import discuss as discuss_blueprint
    from profilee import profile as profile_blueprint
    from neet import neet as neet_blueprint
    # --- This import is now correctly in place ---
    from assessment import assessment_bp

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(problems_blueprint)
    app.register_blueprint(explore_blueprint)
    app.register_blueprint(quiz_blueprint)
    app.register_blueprint(discuss_blueprint)
    app.register_blueprint(profile_blueprint)
    app.register_blueprint(leaderboard_blueprint)
    app.register_blueprint(neet_blueprint)
    # --- This registration is also correctly in place ---
    app.register_blueprint(assessment_bp)

    # ... (the rest of your app context code remains the same)
    with app.app_context():
        db.create_all()

        # Force clear old problems (optional)
        Problem.query.delete()
        db.session.commit()

        # --- Load Problems from JSON File ---
        if not Problem.query.first():
            print("Loading problems from JSON...")
            file_path = os.path.join(os.path.dirname(__file__), 'problems.json')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    problems_data = json.load(f)
                    problems = [Problem(**item) for item in problems_data]
                    db.session.add_all(problems)
                    db.session.commit()
                    print(f"{len(problems)} problems loaded from JSON.")
            else:
                print("problems.json file not found!")
        if not Post.query.first():
            first_user = User.query.first()
            if first_user:
                dummy_posts = [
                    Post(user_id=first_user.id, title="Struggling with Calculus Integrals", content="I'm finding it hard to grasp definite integrals. Any tips or resources beyond the videos?"),
                    Post(user_id=first_user.id, title="Algebra is fun!", content="Just wanted to share how much I enjoyed solving the quadratic equations today. Feeling good about math!"),
                    Post(user_id=first_user.id, title="Quiz difficulty feedback", content="The Algebra quiz was challenging but fair. What do others think?")
                ]
                db.session.add_all(dummy_posts)
                db.session.commit()

    @app.route('/')
    def home():
        return render_template('index.html')
    
    # --- DELETE THE OLD /neet-portal ROUTE FROM HERE ---

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
