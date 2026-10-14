import os
from flask import Flask, redirect, url_for
from app.db import init_app

def create_app(test_config=None):
    app = Flask('app', instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev-secret-key',
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
