from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

try:
    from . import auth
    from .db import DatabaseService
except ImportError:
    import auth
    from db import DatabaseService


bp = Blueprint('pages', __name__)


@bp.route('/attendance', methods=['GET', 'POST'])
def attendance():
    db_service = DatabaseService()
    if auth.is_student():
        student_id = auth.current_user().get('student_id')
        student = db_service.get_one_student(student_id)
        if request.method == 'POST':
            flash('Attendance is read-only for student accounts.', 'error')
            return redirect(url_for('pages.attendance'))
        attendance_records = db_service.get_student_attendance(student_id, limit=30)
        return render_template(
            'attendance/index.html',
            student=student,
            student_attendance=attendance_records,
            read_only=True,
        )

    selected_date = request.values.get('attendanceDate') or date.today().isoformat()
    selected_category = request.values.get('category') or 'all'
    students_list = db_service.all_students()
    students_list = students_list if isinstance(students_list, list) else []
    categories = sorted({
        student.get('category', '')
        for student in students_list
        if student.get('category')
    })
    filtered_students = [
        student
        for student in students_list
        if selected_category == 'all' or student.get('category') == selected_category
    ]

    if request.method == 'POST':
        attendance_rows = {}
        for student in filtered_students:
            student_id = student['id']
            attendance_rows[student_id] = {
                'student_id': student_id,
                'student_name': student.get('name', ''),
                'standard': student.get('standard', ''),
                'category': student.get('category', ''),
                'status': request.form.get(f'status_{student_id}', 'present'),
                'note': request.form.get(f'note_{student_id}', '').strip(),
            }
        result = db_service.save_attendance(selected_date, attendance_rows)
        if result:
            flash('Attendance saved successfully', 'success')
        return redirect(url_for('pages.attendance', attendanceDate=selected_date, category=selected_category))

    attendance_records = db_service.get_attendance_for_date(selected_date)
    return render_template(
        'attendance/index.html',
        selected_date=selected_date,
        selected_category=selected_category,
        categories=categories,
        students=filtered_students,
        attendance_records=attendance_records if isinstance(attendance_records, dict) else {},
    )


@bp.route('/performance', methods=['GET', 'POST'])
def performance():
    db_service = DatabaseService()
    students_list = db_service.all_students()
    students_list = students_list if isinstance(students_list, list) else []

    if auth.is_student():
        student_id = auth.current_user().get('student_id')
        student = db_service.get_one_student(student_id)
        performance_records = db_service.get_student_performance(student_id, limit=30)
        return render_template(
            'performance/index.html',
            students=[],
            student=student,
            performance_records=performance_records,
            read_only=True,
        )

    if request.method == 'POST':
        student_id = request.form.get('studentId', '').strip()
        performance_update = {
            'date': request.form.get('performanceDate', '').strip(),
            'subject': request.form.get('subject', '').strip(),
            'assessment_name': request.form.get('assessmentName', '').strip(),
            'marks': request.form.get('marks', '').strip(),
            'max_marks': request.form.get('maxMarks', '').strip(),
            'grade': request.form.get('grade', '').strip(),
            'note': request.form.get('teacherNote', '').strip(),
            'focus_area': request.form.get('focusArea', '').strip(),
            'created_by': auth.current_user().get('email', ''),
        }
        errors = []
        if not student_id:
            errors.append('Student is required')
        if not performance_update['date']:
            errors.append('Date is required')
        if not performance_update['subject']:
            errors.append('Subject is required')
        if not performance_update['assessment_name']:
            errors.append('Exam or test name is required')
        if not performance_update['marks']:
            errors.append('Marks is required')
        if not performance_update['max_marks']:
            errors.append('Max marks is required')
        if errors:
            flash(errors, 'error')
        else:
            result = db_service.create_performance_update(student_id, performance_update)
            if result:
                flash('Performance update saved successfully', 'success')
                return redirect(url_for('pages.performance'))

    recent_updates = db_service.recent_performance_updates(students_list)
    return render_template('performance/index.html', students=students_list, recent_updates=recent_updates)


@bp.route('/profile')
def profile():
    student = None
    if auth.is_student():
        student = DatabaseService().get_one_student(auth.current_user().get('student_id'))
    return render_template('profile/index.html', student=student)


@bp.route('/chat', methods=['GET', 'POST'])
def chat():
    db_service = DatabaseService()
    current_user = auth.current_user() or {}

    if auth.is_student():
        selected_student_id = current_user.get('student_id')
        selected_student = db_service.get_one_student(selected_student_id)
        selected_student = selected_student if isinstance(selected_student, dict) else None
        students_list = [selected_student] if selected_student else []
    else:
        students_list = db_service.all_students()
        students_list = students_list if isinstance(students_list, list) else []
        selected_student_id = request.values.get('studentId') or (students_list[0]['id'] if students_list else '')
        selected_student = None
        if selected_student_id:
            selected_student = next(
                (student for student in students_list if student.get('id') == selected_student_id),
                None,
            )
            if selected_student is None:
                selected_student = db_service.get_one_student(selected_student_id)
            if not isinstance(selected_student, dict):
                selected_student = None

    if not selected_student:
        if request.method == 'POST':
            flash('Select a student before sending a message.', 'error')
            return redirect(url_for('pages.chat'))
        return render_template(
            'chat/index.html',
            students=students_list,
            selected_student=None,
            messages=[],
        )

    if auth.is_student() and selected_student.get('id') != current_user.get('student_id'):
        flash('You can only view your own chat.', 'error')
        return redirect(url_for('pages.chat'))

    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        if not message:
            flash('Message cannot be empty.', 'error')
        else:
            result = db_service.create_chat_message(
                selected_student['id'],
                selected_student,
                message,
                current_user,
            )
            if isinstance(result, str):
                flash(result, 'error')
            elif result:
                flash('Message sent.', 'success')
        return redirect(url_for('pages.chat', studentId=selected_student['id']))

    messages = db_service.get_chat_messages(selected_student['id'])
    return render_template(
        'chat/index.html',
        students=students_list,
        selected_student=selected_student,
        messages=messages,
    )
