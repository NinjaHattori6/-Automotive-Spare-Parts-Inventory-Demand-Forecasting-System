from pathlib import Path

import click
from flask import Flask

from config import Config
from inventory_app.extensions import db


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from inventory_app import models  # noqa: F401
    from inventory_app.routes import auth, dashboard

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)

    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables without deleting existing data."""
        with app.app_context():
            db.create_all()
        click.echo("Database tables created.")

    @app.context_processor
    def inject_current_user():
        from flask import session
        from inventory_app.models import User

        user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
        return {"current_user": user}

    return app
