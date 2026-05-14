from flask import Flask, jsonify, render_template, request, send_from_directory, redirect, url_for, flash, session
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import hashlib
app = Flask(__name__)
app.secret_key = 'your_secret_key'

word_to_int = {
    "available": "30",
    "unavailable": "0",
}

# Database connection function
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='kiran',
        database='hospital'
    )

@app.route('/')
def index():
    return redirect(url_for('admin_login'))

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Hash the input password
            password_hash = password

            # Query the admin table for matching credentials
            query = "SELECT * FROM admin WHERE admin_id = %s AND password = %s"
            cursor.execute(query, (username, password_hash))
            admin = cursor.fetchone()

            cursor.close()
            conn.close()

            if admin:
                session['admin_logged_in'] = True
                return redirect(url_for('home'))  # Redirect to /admin
            else:
                flash('Invalid username or password. Please try again.')
                return redirect(url_for('admin_login'))

        except Exception as e:
            return render_template("error.html", message=f"Login Error: {str(e)}")

    return render_template('admin_login.html')

@app.route('/admin')
def home():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    return render_template("admin.html")

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route("/patients_records")
def patients_records():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Patient_ID, Name, Gender, DOB, Age, Phone_No FROM patient")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("patients_records.html", patients=data)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory("static", filename)

@app.route('/edit_doctor')
def edit_doctor():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM doctor")
    doctors = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('edit_doctor.html', doctors=doctors)

@app.route('/search_doctor', methods=['GET'])
def search_doctor():
    name = request.args.get('name', '')
    specialization = request.args.get('specialization', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = "SELECT * FROM doctor WHERE 1=1"
    params = []

    if name:
        query += " AND name LIKE %s"
        params.append(f"%{name}%")

    if specialization:
        query += " AND specialization = %s"
        params.append(specialization)

    cursor.execute(query, params)
    doctors = cursor.fetchall()
    cursor.close()
    conn.close()

    if not doctors:
        return jsonify({'error': 'No doctors found.'})
    return jsonify(doctors)

@app.route('/update_doctor', methods=['POST'])
def update_doctor():
    data = request.get_json()

    doctor_name = data.get('doctor_name')  # Get doctor_name from the request
    availability_status = data.get('availability')
    availability = word_to_int.get(availability_status.lower(), -1)
    available_date_str = data.get('available_date')  # Expected format: 'YYYY-MM-DD'
    doc_day = data.get('doc_day')
    doc_time = data.get('doc_time')

    # Check if all required fields are provided
    if not doctor_name or availability == -1 or not available_date_str or not doc_day or not doc_time:
        return jsonify({'error': 'Missing or invalid required fields.'})

    try:
        available_date = datetime.strptime(available_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Expected YYYY-MM-DD.'})

    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Retrieve Doctor_ID based on doctor_name
        cursor.execute("SELECT Doctor_ID FROM doctor WHERE Name = %s", (doctor_name,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Doctor not found.'})
        doctor_id = result[0]

        # Update doc_day and doc_time in the doctor table
        update_doctor_query = """
            UPDATE doctor 
            SET doc_day = %s, doc_time = %s
            WHERE Doctor_ID = %s
        """
        cursor.execute(update_doctor_query, (doc_day, doc_time, doctor_id))

        # Check if an availability record exists for the given date
        check_availability_query = """
            SELECT * FROM doctor_availability
            WHERE Doctor_ID = %s AND Available_Date = %s
        """
        cursor.execute(check_availability_query, (doctor_id, available_date))
        existing_record = cursor.fetchone()

        if existing_record:
            # Update existing availability record
            update_availability_query = """
                UPDATE doctor_availability
                SET Availability = %s
                WHERE Doctor_ID = %s AND Available_Date = %s
            """
            cursor.execute(update_availability_query, (availability, doctor_id, available_date))
        else:
            # Insert new availability record
            insert_availability_query = """
                INSERT INTO doctor_availability (Doctor_ID, Available_Date, Availability)
                VALUES (%s, %s, %s)
            """
            cursor.execute(insert_availability_query, (doctor_id, available_date, availability))

        conn.commit()

        # Close the cursor and connection
        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except Exception as e:
        # Handle any errors (database issues, query problems)
        return jsonify({'error': str(e)})

@app.errorhandler(404)
def page_not_found(e):
    return render_template('edit_doctor.html'), 404

@app.route('/get_all_doctors', methods=['GET'])
def get_all_doctors():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM doctor")
    doctors = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(doctors)

@app.route('/api/pr')
def get_patients():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT Name, Patient_ID FROM patient")
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify([{"Name": row[0], "Patient_ID": row[1]} for row in data])
    except Error as e:
        return jsonify([]), 500

@app.route('/patients_details')
def get_patient_details():
    patient_id = request.args.get('id')
    if not patient_id:
        return render_template("error.html", message="Missing patient ID"), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patient WHERE Patient_ID = %s", (patient_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            patient = {
                "Patient_ID": row[0],
                "Name": row[1],
                "Gender": row[2],
                "DOB": row[3].strftime("%Y-%m-%d") if row[3] else "Not Available",
                "Age": row[4],
                "Phone_No": row[5]
            }
            return render_template("patients_details.html", patient=patient)
        else:
            return render_template("error.html", message="Patient not found"), 404
    except Error as e:
        return render_template("error.html", message=f"Database Error: {str(e)}"), 500

@app.route('/appointments')
def view_appointments():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                a.Appointment_ID, a.Date, a.Time, a.Symptoms,
                d.name AS Doctor_Name, 
                p.Name AS Patient_Name 
            FROM appointment a
            JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
            JOIN patient p ON a.Patient_ID = p.Patient_ID
            ORDER BY a.Date DESC, a.Time DESC
        """
        cursor.execute(query)
        appointments = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("appointments.html", appointments=appointments)
    except Error as e:
        return render_template("error.html", message=f"Database Error: {str(e)}"), 500

@app.route('/add_doctor', methods=['GET', 'POST'])
def add_doctor():
    if request.method == 'POST':
        name = request.form['name']
        specialization = request.form['specialization']
        experience = request.form['experience']
        gender = request.form['gender']
        doc_time = request.form['doc_time']
        doc_day = request.form['doc_day']
        hospital_id = request.form['hospital_id']
        doctor_id = request.form.get('doctor_id', '').strip()  # Optional field

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Check if doctor with same details already exists in the database
            query_check = """
                SELECT * FROM doctor
                WHERE Name = %s AND Specialization = %s AND Experience = %s 
                AND Gender = %s AND Hospital_ID = %s
            """
            cursor.execute(query_check, (name, specialization, experience, gender, hospital_id))
            existing_doctor = cursor.fetchone()

            if existing_doctor:
                # If a doctor already exists, show a message and do not add the doctor
                return render_template('add_doctor.html', message="This doctor already exists in the database.")

            # If doctor_id is not provided, generate a new one like adr001, adr002, ...
            if not doctor_id:
                cursor.execute("SELECT Doctor_ID FROM doctor WHERE Doctor_ID LIKE 'adr%' ORDER BY Doctor_ID DESC LIMIT 1")
                latest = cursor.fetchone()
                if latest:
                    latest_id = int(latest[0][3:])  # Extract number from adrXXX
                    doctor_id = f"adr{latest_id + 1:03d}"
                else:
                    doctor_id = "adr001"

            # Insert new doctor data into the doctor table
            query_insert = """
                INSERT INTO doctor (Doctor_ID, Name, Specialization, Experience, Gender, Hospital_ID, doc_time, doc_day)
                VALUES (%s, %s, %s, %s, %s, %s,
::contentReference[oaicite:0]{index=0}%s, %s)
            """
            cursor.execute(query_insert, (
                doctor_id, name, specialization, experience,
                gender, hospital_id, doc_time, doc_day
            ))

            conn.commit()

            return render_template('add_doctor.html', message="Doctor added successfully!")

        except Exception as e:
            return render_template('add_doctor.html', message=f"Error: {str(e)}")

        finally:
            cursor.close()
            conn.close()

    return render_template('add_doctor.html')

 
if __name__ == '__main__':
    app.run(debug=True)
