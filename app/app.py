import os
import logging
from flask import Flask, redirect, url_for
from app.db import init_app

logger = logging.getLogger(__name__)

def create_app(test_config=None):
    app = Flask('app', instance_relative_config=True)

    secret_key = os.environ.get('SECRET_KEY')
    is_production = bool(
        os.environ.get('DB_SECRET_NAME')
        or os.environ.get('DB_HOST')
        or os.environ.get('FLASK_ENV') == 'production'
    )
    if not secret_key:
        if is_production:
            logger.warning(
                "SECURITY WARNING: SECRET_KEY environment variable is not set in production. "
                "Using fallback development key. Set a persistent SECRET_KEY to secure sessions."
            )
        secret_key = 'dev-secret-key'

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        DATABASE=os.path.join(app.instance_path, 'event_management.db'),
        UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'),
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)





    # Ensure instance and upload folders exist
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
        
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'])
    except OSError:
        pass

    init_app(app)

    # Register S3/file URL helper for Jinja templates
    from app.s3 import get_file_url
    app.jinja_env.globals['file_url'] = get_file_url
    app.jinja_env.filters['file_url'] = get_file_url

    # Register blueprints
    from app.blueprints import auth, faculty, admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(faculty.bp)
    app.register_blueprint(admin.bp)

    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
