import base64
import hmac
import json
import os
import secrets
from functools import wraps

from firebase_admin import auth as firebase_auth
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for

try:
    from .db import DatabaseService, initialize_firebase_app
except ImportError:
    from db import DatabaseService, initialize_firebase_app


bp = Blueprint('auth', __name__, url_prefix='/auth')
CSRF_EXEMPT_ENDPOINTS = {'auth.create_session'}
CSRF_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def token_project_details(id_token):
    try:
        payload = id_token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
        return {
            'audience': claims.get('aud'),
            'issuer': claims.get('iss'),
        }
    except (IndexError, ValueError, TypeError, json.JSONDecodeError):
        return {'audience': None, 'issuer': None}


def firebase_web_config():

    return {
        'apiKey': os.environ.get('FIREBASE_WEB_API_KEY', 'AIzaSyAEm9jRCW2OsqQlvbNrUi2yfI-3OVkzk9E'),
        'authDomain': os.environ.get('FIREBASE_AUTH_DOMAIN', 'tution-master-79288.firebaseapp.com'),
        'projectId': os.environ.get('FIREBASE_PROJECT_ID', 'tution-master-79288'),
        'storageBucket': os.environ.get('FIREBASE_STORAGE_BUCKET', 'tution-master-79288.firebasestorage.app'),
        'messagingSenderId': os.environ.get('FIREBASE_MESSAGING_SENDER_ID', '1005304531496'),
        'appId': os.environ.get('FIREBASE_WEB_APP_ID', '1:1005304531496:web:78aaf42402357ca383c31d'),
        'measurementId': os.environ.get('FIREBASE_MEASUREMENT_ID', 'G-M8XRL78TWM')
    }


def admin_emails():
    raw_emails = os.environ.get('ADMIN_EMAILS') or os.environ.get('ADMIN_EMAIL') or ''
    return {
        email.strip().lower()
        for email in raw_emails.split(',')
        if email.strip()
    }


def current_user():
    return session.get('user')


def csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def validate_csrf_request():
    if request.method not in CSRF_METHODS:
        return None
    if request.endpoint in CSRF_EXEMPT_ENDPOINTS:
        return None

    expected_token = session.get('_csrf_token')
    supplied_token = request.form.get('_csrf_token') or request.headers.get('X-CSRFToken')
    if not expected_token or not supplied_token or not hmac.compare_digest(expected_token, supplied_token):
        return abort(400, description='Invalid CSRF token.')
    return None


def is_admin():
    user = current_user()
    return bool(user and user.get('role') == 'admin')


def is_student():
    user = current_user()
    return bool(user and user.get('role') == 'student')


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user():
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user():
            return redirect(url_for('auth.login'))
        if not is_admin():
            flash('You do not have access to that page.', 'error')
            return redirect(url_for('index'))
        return view(*args, **kwargs)

    return wrapped_view


def token_has_admin_claim(decoded_token):
    return decoded_token.get('admin') is True


def firebase_user_admin_claim(user_record):
    claims = user_record.custom_claims or {}
    return claims.get('admin') is True


def set_admin_claim(email, enabled=True):
    normalized_email = email.lower().strip()
    user_record = firebase_auth.get_user_by_email(normalized_email)
    custom_claims = user_record.custom_claims or {}

    if enabled:
        custom_claims['admin'] = True
    else:
        custom_claims.pop('admin', None)

    firebase_auth.set_custom_user_claims(user_record.uid, custom_claims or None)
    return user_record


def sync_bootstrap_admin_claim(email):
    if email not in admin_emails():
        return

    try:
        user_record = firebase_auth.get_user_by_email(email)
        if not firebase_user_admin_claim(user_record):
            set_admin_claim(email, True)
    except Exception as error:
        current_app.logger.warning('Unable to sync Firebase admin claim for %s: %s', email, error)


def admin_users():
    initialize_firebase_app()
    bootstrap_admins = admin_emails()
    rows = {}

    for page in firebase_auth.list_users().iterate_all():
        email = (page.email or '').lower()
        if not email:
            continue
        has_claim = firebase_user_admin_claim(page)
        if has_claim or email in bootstrap_admins:
            rows[email] = {
                'email': email,
                'uid': page.uid,
                'display_name': page.display_name or '',
                'claim_admin': has_claim,
                'bootstrap_admin': email in bootstrap_admins,
            }

    for email in bootstrap_admins:
        rows.setdefault(email, {
            'email': email,
            'uid': '',
            'display_name': '',
            'claim_admin': False,
            'bootstrap_admin': True,
        })

    return sorted(rows.values(), key=lambda row: row['email'])


@bp.route('/login')
def login():
    if current_user():
        return redirect(url_for('index'))
    return render_template('auth/login.html', firebase_config=firebase_web_config())


@bp.route('/session', methods=['POST'])
def create_session():
    id_token = request.json.get('idToken') if request.is_json else None
    if not id_token:
        return jsonify({'success': False, 'message': 'Missing Firebase token.'}), 400

    try:
        initialize_firebase_app()
        decoded_token = firebase_auth.verify_id_token(id_token, clock_skew_seconds=5)
    except firebase_auth.ExpiredIdTokenError:
        current_app.logger.warning('Firebase sign-in failed: expired ID token.')
        return jsonify({
            'success': False,
            'message': 'Your Google sign-in expired. Please try signing in again.',
        }), 401
    except firebase_auth.RevokedIdTokenError:
        current_app.logger.warning('Firebase sign-in failed: revoked ID token.')
        return jsonify({
            'success': False,
            'message': 'This Google sign-in is no longer valid. Please sign in again.',
        }), 401
    except firebase_auth.CertificateFetchError:
        current_app.logger.exception('Firebase sign-in failed while fetching Google certificates.')
        return jsonify({
            'success': False,
            'message': 'The server could not contact Google to verify your sign-in. Please try again.',
        }), 503
    except firebase_auth.InvalidIdTokenError as error:
        token_details = token_project_details(id_token)
        current_app.logger.exception(
            'Firebase rejected the ID token: %s; expected_project=%s; token_audience=%s; token_issuer=%s',
            error,
            firebase_web_config()['projectId'],
            token_details['audience'],
            token_details['issuer'],
        )
        return jsonify({
            'success': False,
            'message': 'Firebase rejected the sign-in token. Check that the Web SDK config and Admin SDK use the same Firebase project.',
        }), 401
    except Exception as error:
        current_app.logger.exception('Unexpected Firebase sign-in verification error: %s', error)
        return jsonify({
            'success': False,
            'message': 'Unable to verify your Google sign-in. Check the application server log for the exact Firebase error.',
        }), 401

    email = decoded_token.get('email', '').lower()
    uid = decoded_token.get('uid', '')
    name = decoded_token.get('name') or email

    db_service = DatabaseService()
    linked_student = db_service.find_student_by_user(email=email, uid=uid)

    if token_has_admin_claim(decoded_token) or email in admin_emails():
        sync_bootstrap_admin_claim(email)
        session['user'] = {
            'email': email,
            'uid': uid,
            'name': name,
            'role': 'admin',
        }
        return jsonify({'success': True, 'redirect': url_for('index')})

    if linked_student:
        if not linked_student.get('user_uid') and uid:
            db_service.update_student(linked_student['id'], {'user_uid': uid})
        session['user'] = {
            'email': email,
            'uid': uid,
            'name': name,
            'role': 'student',
            'student_id': linked_student['id'],
            'student_name': linked_student.get('name', ''),
        }
        return jsonify({'success': True, 'redirect': url_for('index')})

    return jsonify({
        'success': False,
        'message': 'This Gmail address has not been approved for this tuition account.',
    }), 403


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@bp.route('/admins', methods=['GET', 'POST'])
@admin_required
def admins():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        action = request.form.get('action', 'grant')

        if not email:
            flash('Email is required.', 'error')
            return redirect(url_for('auth.admins'))

        if action == 'revoke' and email == current_user().get('email') and email not in admin_emails():
            flash('You cannot revoke your own only admin claim while signed in.', 'error')
            return redirect(url_for('auth.admins'))

        try:
            set_admin_claim(email, enabled=(action != 'revoke'))
            if action == 'revoke':
                flash(f'Admin access removed for {email}. They must sign in again for this to take effect.', 'success')
            else:
                flash(f'Admin access granted to {email}. They must sign in again or refresh their token.', 'success')
        except firebase_auth.UserNotFoundError:
            flash(f'No Firebase Auth user found for {email}. Ask them to sign in once first.', 'error')
        except Exception as error:
            current_app.logger.exception('Unable to update admin claim for %s: %s', email, error)
            flash('Unable to update Firebase admin access. Check the server log for details.', 'error')
        return redirect(url_for('auth.admins'))

    return render_template('auth/admins.html', admins=admin_users())
