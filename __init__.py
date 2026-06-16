import os

from flask import Flask, redirect, render_template, request, session, url_for
from flasgger import Swagger, LazyString
try:
    from . import auth, pages, students
    from .db import DatabaseService
    from .utils import UtilityService
except ImportError:
    import auth
    import pages
    import students
    from db import DatabaseService
    from utils import UtilityService

utilityService = UtilityService() 


def production_mode():
    return os.environ.get('FLASK_ENV') == 'production' or os.environ.get('APP_ENV') == 'production'

def create_app():
    app = Flask(__name__)
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key and production_mode():
        raise RuntimeError('SECRET_KEY must be set in production.')
    app.secret_key = secret_key or utilityService.randomize_string(30)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax'),
        SESSION_COOKIE_SECURE=production_mode(),
        PREFERRED_URL_SCHEME='https' if production_mode() else 'http',
    )

    swag_template = {
        "swagger": "2.0",
        "title": LazyString(lambda: 'MH Tuition'),
        "version": LazyString(lambda: '1.0.0'),
        "description": LazyString(lambda: 'Application for MH Tuition'),
        "termsOfService": LazyString(lambda: '/terms'),
        "schemes": [LazyString(lambda: 'https' if request.is_secure else 'http')],
        "basePath": os.environ.get('SWAGGER_BASE_PATH', 'http://localhost:5000')
    }
    swag_config = {
        "headers": [
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', "GET, POST"),
        ],
        "specs": [
            {
                "endpoint": 'MH Tuition',
                "route": '/apiStudents.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/",
    }

    @app.route('/')
    @auth.login_required
    def index():
        if auth.is_student():
            return redirect(url_for('students.one_student', id=session['user']['student_id']))
        db_service = DatabaseService()
        students_list = db_service.all_students()
        attendance_summary = db_service.attendance_summary()
        return render_template(
            'main.html',
            students=students_list if isinstance(students_list, list) else [],
            attendance_summary=attendance_summary,
        )

    @app.before_request
    def require_signed_in_user():
        public_endpoint_prefixes = ('auth.', 'flasgger.', 'static')
        public_paths = ('/apidocs/', '/apispec_1.json', '/apiStudents.json')
        endpoint = request.endpoint or ''
        csrf_error = auth.validate_csrf_request()
        if csrf_error:
            return csrf_error
        if endpoint.startswith(public_endpoint_prefixes) or request.path in public_paths:
            return None
        if not session.get('user'):
            return redirect(url_for('auth.login'))
        return None

    @app.context_processor
    def inject_user_context():
        return {
            'current_user': auth.current_user(),
            'is_admin': auth.is_admin(),
            'is_student': auth.is_student(),
            'csrf_token': auth.csrf_token,
        }
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(students.bp)
    app.register_blueprint(pages.bp)
    if os.environ.get('ENABLE_SWAGGER', '').lower() in ('1', 'true', 'yes'):
        swagger = Swagger(app=app, template=swag_template, config=swag_config)

    return app
