import json
import os

from flask import jsonify, request
from datetime import date
from firebase_admin import firestore, credentials, get_app, initialize_app


def initialize_firebase_app():
    try:
        return get_app()
    except ValueError:
        service_account_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
        service_account_path = (
            os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH')
            or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        )
        project_id = os.environ.get('FIREBASE_PROJECT_ID')
        options = {'projectId': project_id} if project_id else None

        if service_account_json:
            cred = credentials.Certificate(json.loads(service_account_json))
        elif service_account_path:
            cred = credentials.Certificate(service_account_path)
        else:
            cred = credentials.ApplicationDefault()
        return initialize_app(cred, options=options)

class DatabaseService:
    def __init__(self):
        # firebase.FirebaseTokenGenerator
        initialize_firebase_app()
        self.db = firestore.client()
        self.student_ref = self.db.collection('students')
        self.attendance_ref = self.db.collection('attendance')

    def all_students(self):
        # Get all the documents from the database
        try:
            self.all_students = []
            for doc in self.student_ref.stream():
                student = doc.to_dict()
                student['id'] = doc.id
                self.all_students.append(student)
            return self.all_students
        except Exception as e:
            return f"An Error occurred while reading database: {e}"
        
    def get_one_student(self, id):
        # Get information about one specific student
        try:
            self.my_student = self.student_ref.document(id).get().to_dict()
            if isinstance(self.my_student, dict):
                self.my_student['id'] = id
            return self.my_student
        except Exception as e:
            return f"Error while fetching student information: {e}"

    def find_student_by_user(self, email='', uid=''):
        try:
            normalized_email = email.lower().strip()
            if uid:
                for doc in self.student_ref.where('user_uid', '==', uid).limit(1).stream():
                    student = doc.to_dict()
                    student['id'] = doc.id
                    return student
            if normalized_email:
                for doc in self.student_ref.where('user_email', '==', normalized_email).limit(1).stream():
                    student = doc.to_dict()
                    student['id'] = doc.id
                    return student
            return None
        except Exception:
            return None
        
    def create_student(self, new_document_id, new_student):
        # Create a new student profile
        try:
            id = self.student_ref.document(new_document_id).set(new_student)
            return jsonify({"success": True, "id": id}), 200
        except Exception as e:
            return f"Error while writing to database: {e}"
        
    def delete_student(self, selected_studentId):
        # Delete the selected student
        try:
            self.student_ref.document(selected_studentId).delete()
            return jsonify({"success": True}), 200
        except Exception as e:
            return f"Error while deleting the student: {e}"

    def update_student(self, selected_studentId, updated_student):
        # Update student information
        try:
            self.student_ref.document(selected_studentId).update(updated_student)
            return jsonify({"success": True}), 200
        except Exception as e:
            return f"Error while updating the student: {e}"

    def get_attendance_for_date(self, selected_date):
        try:
            records = {}
            for doc in self.attendance_ref.document(selected_date).collection('students').stream():
                record = doc.to_dict()
                record['student_id'] = doc.id
                records[doc.id] = record
            return records
        except Exception as e:
            return f"Error while fetching attendance: {e}"

    def save_attendance(self, selected_date, attendance_rows):
        try:
            batch = self.db.batch()
            day_ref = self.attendance_ref.document(selected_date)
            batch.set(day_ref, {
                'date': selected_date,
                'updated_at': firestore.SERVER_TIMESTAMP,
            }, merge=True)
            for student_id, row in attendance_rows.items():
                batch.set(day_ref.collection('students').document(student_id), row, merge=True)
            batch.commit()
            return jsonify({"success": True}), 200
        except Exception as e:
            return f"Error while saving attendance: {e}"

    def get_student_attendance(self, student_id, limit=12):
        try:
            records = []
            for day_doc in self.attendance_ref.order_by('date', direction=firestore.Query.DESCENDING).limit(limit).stream():
                record_doc = day_doc.reference.collection('students').document(student_id).get()
                if record_doc.exists:
                    record = record_doc.to_dict()
                    record['date'] = day_doc.id
                    records.append(record)
            return records
        except Exception:
            return []

    def create_performance_update(self, student_id, update):
        try:
            doc_ref = self.student_ref.document(student_id).collection('performance').document()
            update['created_at'] = firestore.SERVER_TIMESTAMP
            doc_ref.set(update)
            return jsonify({"success": True, "id": doc_ref.id}), 200
        except Exception as e:
            return f"Error while saving performance update: {e}"

    def get_student_performance(self, student_id, limit=20):
        try:
            records = []
            query = (
                self.student_ref
                .document(student_id)
                .collection('performance')
                .order_by('date', direction=firestore.Query.DESCENDING)
                .limit(limit)
            )
            for doc in query.stream():
                record = doc.to_dict()
                record['id'] = doc.id
                records.append(record)
            return records
        except Exception:
            return []

    def recent_performance_updates(self, students_list, limit_per_student=3):
        records = []
        for student in students_list:
            student_id = student.get('id')
            if not student_id:
                continue
            for record in self.get_student_performance(student_id, limit_per_student):
                record['student_id'] = student_id
                record['student_name'] = student.get('name', '')
                record['standard'] = student.get('standard', '')
                records.append(record)
        return sorted(records, key=lambda row: row.get('date', ''), reverse=True)

    def attendance_summary(self):
        try:
            selected_date = date.today().isoformat()
            records = self.get_attendance_for_date(selected_date)
            if not isinstance(records, dict):
                return {'date': selected_date, 'present': 0, 'absent': 0, 'late': 0, 'excused': 0, 'total': 0}
            summary = {'date': selected_date, 'present': 0, 'absent': 0, 'late': 0, 'excused': 0, 'total': len(records)}
            for record in records.values():
                status = record.get('status', 'present')
                if status in summary:
                    summary[status] += 1
            return summary
        except Exception:
            return {'date': date.today().isoformat(), 'present': 0, 'absent': 0, 'late': 0, 'excused': 0, 'total': 0}
        
