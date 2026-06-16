from flask import (Blueprint, g, flash, redirect, render_template, request, Response, url_for)
from werkzeug.exceptions import abort
try:
    from . import auth
    from .db import DatabaseService
    from .utils import UtilityService
except ImportError:
    import auth
    from db import DatabaseService
    from utils import UtilityService
from flasgger import swag_from

bp = Blueprint('students', __name__)

@bp.route('/students/all', methods=['GET'])
@swag_from("docs/students.yaml")
@auth.admin_required
def all_students():
    dbService = DatabaseService()
    students_list = dbService.all_students()
    return render_template('students/index.html', students=students_list if isinstance(students_list, list) else [])

@bp.route('/students/<id>', methods=['GET'])
@swag_from("docs/student_one.yaml")
@swag_from("docs/student_one.yaml")
def one_student(id):
    if auth.is_student() and auth.current_user().get('student_id') != id:
        flash('You can only view your own profile.', 'error')
        return redirect(url_for('index'))
    dbService = DatabaseService()
    my_student = dbService.get_one_student(id)
    attendance_records = dbService.get_student_attendance(id)
    performance_records = dbService.get_student_performance(id)
    return render_template(
        'students/view.html',
        student=my_student,
        attendance_records=attendance_records,
        performance_records=performance_records,
    )

@bp.route('/students/new', methods=['GET', 'POST'])
@swag_from({
    'responses': [
        {
            "200": {
                'description': 'Create a new student'
            }
        }
    ]
})
@auth.admin_required
def create_student():
    dbService = DatabaseService()
    utilityService = UtilityService()
    if request.method == 'POST':
        # pass the value of form elements as a json
        # to the below method
        name = request.form['inputName']
        mobile = request.form['inputMobile']
        standard = request.form['inputStandard']
        school = request.form['inputSchool']
        father_name = request.form['inputFatherName']
        mother_name = request.form['inputMotherName']
        date_of_birth = request.form.get('inputDateOfBirth', '').strip()
        category = request.form['inputCategory']
        fees = request.form['inputFees']
        user_email = request.form.get('inputUserEmail', '').lower().strip()
        user_uid = request.form.get('inputUserUid', '').strip()
        errors = []

        if not name:
            errors.append('Name is required')
        if not mobile:
            errors.append('Mobile is required')
        if not(len(mobile) == 10):
            errors.append('Mobile number should be 10 digits')
        if not standard:
            errors.append('Standard is required')
        if not school:
            errors.append('School is required')
        if not father_name:
            errors.append('Father name is required')
        if not mother_name:
            errors.append('Mother name is required')
        if not category:
            errors.append('Category is required')
        if not fees:
            errors.append('Fees is required')
        
        if len(errors) == 0:
            random_string_id = utilityService.randomize_string(20)
            new_student = {
                "name": f"{name}",
                "mobile": f"{mobile}",
                "standard": f"{standard}",
                "school": f"{school}",
                "father_name": f"{father_name}",
                "mother_name": f"{mother_name}",
                "date_of_birth": f"{date_of_birth}",
                "category": f"{category}",
                "fees": f"{fees}",
                "user_email": f"{user_email}",
                "user_uid": f"{user_uid}",
            }
            result = dbService.create_student(random_string_id, new_student)
            if (result):
                flash('New Student saved successfully', 'success')
                return redirect(url_for('students.all_students'))
            else:
                return f"Create Form rendered here"
        flash(errors, 'error')
    return render_template('students/create.html')

@bp.route('/students/<id>/update', methods=['GET', 'POST'])
@swag_from({
    'parameters': [
        {
            'name': 'id',
            'in': 'path',
            'type': 'string',
            'required': True,
            'description': 'Id to update infomation about the required student'
        }
    ],
    'responses': [
        {
            "200": {
                'description': 'Updated student information'
            }
        }
    ]
})
@auth.admin_required
def update_student(id):
    dbService = DatabaseService()
    edit_student = dbService.get_one_student(id)
    if request.method == 'POST':
        # pass the value of form elements as a json
        # to the below method
        name = request.form['inputName']
        mobile = request.form['inputMobile']
        standard = request.form['inputStandard']
        school = request.form['inputSchool']
        father_name = request.form['inputFatherName']
        mother_name = request.form['inputMotherName']
        date_of_birth = request.form.get('inputDateOfBirth', '').strip()
        category = request.form['inputCategory']
        fees = request.form['inputFees']
        user_email = request.form.get('inputUserEmail', '').lower().strip()
        user_uid = request.form.get('inputUserUid', '').strip()
        errors = []

        if not name:
            errors.append('Name is required')
        if not mobile:
            errors.append('Mobile is required')
        if len(mobile) < 10 or len(mobile) > 10:
            errors.append('Mobile number should be 10 digits')
        if not standard:
            errors.append('Standard is required')
        if not school:
            errors.append('School is required')
        if not father_name:
            errors.append('Father name is required')
        if not mother_name:
            errors.append('Mother name is required')
        if not category:
            errors.append('Category is required')
        if not fees:
            errors.append('Fees is required')
        if len(errors) == 0:
            updated_student = {
                "name": f"{name}",
                "mobile": f"{mobile}",
                "standard": f"{standard}",
                "school": f"{school}",
                "father_name": f"{father_name}",
                "mother_name": f"{mother_name}",
                "date_of_birth": f"{date_of_birth}",
                "category": f"{category}",
                "fees": f"{fees}",
                "user_email": f"{user_email}",
                "user_uid": f"{user_uid}",
            }
            result = dbService.update_student(id, updated_student)
            if result:
                flash("Student information updated successfully", 'success')
                # Update successfully completed
                # control passed to home page
                return redirect(url_for('students.all_students'))
            else:
                # If error while updating, use this to throw error
                return f"Edit Form rendered here"
        flash(errors, 'error')
    return render_template('students/update.html', studentId=id, student=edit_student)

@bp.route('/students/<id>/delete', methods=['DELETE'])
@swag_from({
    'parameters': [
        {
            'name': 'id',
            'in': 'path',
            'type': 'string',
            'required': True,
            'description': 'Id to delete the required student'
        }
    ],
    'responses': [
        {
            "200": {
                'description': 'Delete the selected student'
            },
            "400": {
                'description': 'Bad request'
            }
        }
    ]
})
@auth.admin_required
def delete_student(id):
    dbService = DatabaseService()
    result = dbService.delete_student(id)
    return result
