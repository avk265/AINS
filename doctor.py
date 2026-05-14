from flask import Flask, request, redirect, url_for, render_template, session, flash, jsonify
from werkzeug.security import generate_password_hash
import threading
import webview
import mysql.connector
import bcrypt
import random
import os
import string
from datetime import timedelta
from datetime import date
app = Flask(__name__)

app.secret_key = os.urandom(24)  # Required for flash messages
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.jinja_env.globals.update(random=lambda: random.random())  


def get_db_connection():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="kiran",
            database="hospital"
        )
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None  # Return None if connection fails

@app.route('/twitter')
def twitter():
    return redirect("https://www.twitter.com")
@app.route('/fb')
def fb():
    return redirect("https://www.facebook.com")
@app.route('/logout')
def logout():
    session.clear()  # Clear the session data
    flash("You have been logged out.", "success")
    return redirect(url_for('home'))

#Home Route
@app.route('/')
@app.route('/home')
def home():
    return render_template('ad1.html')

@app.route('/about-us') 
def about():
    return render_template('about.html')

@app.route('/contact') 
def contact():
    return render_template('contact us.html')

@app.route("/get_doctors", methods=["GET"])
def get_doctors():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT doctor_id AS id, name FROM doctors")
    doctors = cursor.fetchall()
    conn.close()
    return jsonify(doctors)

@app.route('/get_top_doctor', methods=['GET'])
def get_top_doctor():
    specialization = request.args.get('specialization', "")
    hospital = request.args.get('hospital', "All")
    
    if not specialization:
        return jsonify({"error": "Specialization not provided"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT d.name, d.specialization, d.experience, d.doc_time, d.doctor_id, d.doc_day, d.hospital_id
        FROM doctor d 
        WHERE d.specialization = %s
    """
    params = [specialization]

    if hospital != "All":
        query += " AND d.hospital_id = %s"
        params.append(hospital)

    query += " ORDER BY d.experience DESC LIMIT 1"
    cursor.execute(query, tuple(params))
    top_doctor = cursor.fetchone()

    cursor.close()
    conn.close()
    return jsonify(top_doctor if top_doctor else {"error": "No doctor found"}), 200


@app.route("/get_doctor_details", methods=["GET"])
def get_doctor_details():
    doctor_id = request.args.get("id")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, specialization FROM doctor WHERE doctor_id = %s", (doctor_id,))
    doctor = cursor.fetchone()
    conn.close()
    return jsonify(doctor)

@app.route("/get_patients", methods=["GET"])
def get_patients():
    user_id = request.args.get("user_id")  # Retrieve user_id from session
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT patient_id AS id, name FROM patients WHERE user_id = %s", (user_id,))
    patients = cursor.fetchall()
    conn.close()
    return jsonify(patients)

@app.route("/get_patient_details", methods=["GET"])
def get_patient_details():
    patient_id = request.args.get("id")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, phone, email, gender FROM patients WHERE patient_id = %s", (patient_id,))
    patient = cursor.fetchone()
    conn.close()
    return jsonify(patient)

@app.route('/doctors')
def doctors():
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
    d.Doctor_ID, 
    d.Name, 
    d.Specialization, 
    d.Experience,
    d.Hospital_ID,
    d.doc_day, 
    d.doc_time, 
    da.Availability
FROM doctor d
JOIN doctor_availability da 
    ON d.Doctor_ID = da.Doctor_ID
WHERE da.Availability > 0
AND da.Available_Date = (
    SELECT MAX(Available_Date) 
    FROM doctor_availability 
    WHERE Doctor_ID = d.Doctor_ID
);


    """)
    
    doctors = cursor.fetchall()
    conn.close()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Hospital_ID, Name FROM hospital")
    hospitals = cursor.fetchall()
    conn.close()

    return render_template('doctors.html', doctors=doctors, hospitals=hospitals)

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Hospital_ID, Name FROM hospital")
    hospitals = cursor.fetchall()
    conn.close()

    return render_template('doctors.html', hospitals=hospitals)

@app.route('/filter_doctors', methods=['GET'])
def filter_doctors():
    # Get query parameters
    specialization = request.args.get('specialization', '')
    hospital = request.args.get('hospital', 'All')
    experience = request.args.get('experience', '')

    # Base query with no filters
    query = "SELECT * FROM doctor WHERE 1=1"
    params = []

    # Filter by specialization if provided
    if specialization:
        query += " AND specialization = %s"
        params.append(specialization)
    
    # Filter by hospital if provided (except 'All')
    if hospital != 'All':
        query += " AND hospital_id = %s"
        params.append(hospital)
    
    # Validate and filter by experience if provided
    if experience:
        try:
            experience = int(experience)  # Convert to integer
            query += " AND experience >= %s"
            params.append(experience)
        except ValueError:
            return jsonify({"error": "Invalid experience value"}), 400

    # Fetch doctors from the database
    doctors = get_doctors_from_db(query, params)
    
    # If no doctors found, return an appropriate response
    if not doctors:
        return jsonify({"message": "No doctors found"}), 404

    # Return doctors as JSON response
    return jsonify(doctors)

# Helper function to get doctors from the database
def get_doctors_from_db(query, params):
    conn=get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()  # Returns the rows (you may need to format it as needed)
@app.route('/appointment')
def appointment():
    print("Session Data:", session)  # Debugging
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    if 'selected_patient_id' not in session:
        flash("Please select a patient first.", "warning")
        return redirect(url_for('select_patient'))

    doctor_id = request.args.get('doctor_id')  
    patient_id = session['selected_patient_id'] 


    doctor = None
    patient = None
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)


    if doctor_id:
        cursor.execute("SELECT name, specialization, doc_day FROM doctor WHERE doctor_id = %s", (doctor_id,))
        doctor = cursor.fetchone() or {}

    if patient_id:
        cursor.execute("""
            SELECT p.name, p.phone_no, p.gender, u.email 
            FROM patient p
            JOIN accounts a ON p.patient_id = a.patient_id
            JOIN users u ON a.account_id = u.user_id  
            WHERE p.patient_id = %s
        """, (patient_id,))
        patient = cursor.fetchone() or {}

    conn.close()
    return render_template('appointment.html', doctor=doctor, patient=patient)

@app.route('/add_user', methods=['GET'])
def add_user_form():
    return render_template('add_user.html')

from datetime import datetime

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        gender = request.form['gender']
        dob = request.form['dob']
        phone = request.form['phone']
        user_id = session['user_id']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if patient already exists (case-insensitive)
        cursor.execute("SELECT COUNT(*) FROM patient WHERE BINARY LOWER(Name) = LOWER(%s)", (name,))
        existing_patient_count = cursor.fetchone()[0]

        if existing_patient_count > 0:
            flash("A patient with the same name already exists!", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('add_user', mode=request.args.get('mode', '')))

        new_patient_id = generate_patient_id()
        age = calculate_age(dob)

        try:
            # Insert new patient with lowercase name
            cursor.execute(
                "INSERT INTO patient (Patient_ID, Name, Gender, DOB, Age, Phone_No) VALUES (%s, LOWER(%s), %s, %s, %s, %s)",
                (new_patient_id, name, gender, dob, age, phone)
            )

            cursor.execute("INSERT INTO accounts (Account_ID, Patient_ID) VALUES (%s, %s)", (user_id, new_patient_id))

            conn.commit()
            flash("New patient added successfully!", "success")

        except Exception as e:
            conn.rollback()
            flash(f"Error adding patient: {str(e)}", "danger")

        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('select_patient', mode=request.args.get('mode', '')))

    return render_template("add_user.html")


@app.route('/save_appointment', methods=['POST'])
def save_appointment():
    if 'user_id' not in session:
        flash("Please log in first!", "danger")
        return redirect(url_for('login'))

    print("Received Form Data:", request.form.to_dict())

    doctor_id = request.form.get("doctor_id")
    if not doctor_id:
        flash("Doctor ID is missing!", "danger")
        return redirect(url_for("appointment"))
    if request.method == 'POST':
        date = request.form.get('date')
        symptoms = request.form.get('symp')
        patient_name = request.form.get('patient_name')  # From the form
        time = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
        conn = get_db_connection()
        if conn is None:
            flash("Database connection failed!", "danger")
            return redirect(url_for('appointment'))

        try:
            print("Received doctor_id:", doctor_id)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT doctor_id FROM doctor WHERE doctor_id = %s", (doctor_id,))
            doctor = cursor.fetchone()
            if not doctor:
                flash("Doctor not found!", "danger")
                return redirect(url_for('appointment')) 


            cursor.execute("SELECT patient_id FROM patient WHERE name = %s", (patient_name,))
            patient = cursor.fetchone()
            if not patient:
                flash("Patient not found!", "danger")
                return redirect(url_for('logout'))
            patient_id = patient['patient_id']

            query = """INSERT INTO appointment (Date, Time, Symptoms, Doctor_ID, Patient_ID) 
                       VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(query, (date, time, symptoms, doctor_id, patient_id))
            conn.commit()

            return jsonify({"success": True, "message": "Appointment booked successfully!"})
            return redirect(url_for('home'))

        except Exception as e:
            print("Error:", e)
            flash("Failed to book appointment. Try again!", "danger")
            return jsonify({"success": False, "message": "Failed to book appointment. Try again!"}), 500

        finally:
            cursor.close()
            conn.close()

    return redirect(url_for('doctors'))


@app.route('/appointment_history')
def appointment_history():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))
    
    if 'selected_patient_id' not in session:
        flash("Please select a patient first.", "warning")
        return redirect(url_for('select_patient'))

    selected_patient_id = session['selected_patient_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all appointments for the patient with doctor and token status info
    cursor.execute("""
        WITH LatestCompleted AS (
            SELECT Doctor_ID, MAX(Token_Number) AS Last_Completed_Token
            FROM tokens
            WHERE Status = 'Consulted'
            GROUP BY Doctor_ID
        )
        SELECT 
            a.Appointment_Number, 
            a.Date, 
            a.Time, 
            a.Token_Number, 
            a.Doctor_ID,
            a.Patient_ID,
            d.Name AS Doctor_Name, 
            d.Specialization,
            COALESCE(lc.Last_Completed_Token, 0) AS Last_Completed_Token,
            CASE 
                WHEN a.Token_Number <= COALESCE(lc.Last_Completed_Token, 0) 
                THEN 'Completed' 
                ELSE 'Upcoming' 
            END AS Status
        FROM appointment a
        JOIN doctor d ON a.Doctor_ID = d.Doctor_ID
        LEFT JOIN LatestCompleted lc ON a.Doctor_ID = lc.Doctor_ID
        WHERE a.Patient_ID = %s
        ORDER BY a.Date DESC, a.Time DESC
    """, (selected_patient_id,))
    appointments = cursor.fetchall()

    # Fetch consultation status tokens
    cursor.execute("SELECT doctor_id, patient_id, appointment_date, status FROM tokens")
    tokens = cursor.fetchall()

    token_lookup = {}
    for token in tokens:
        doctor_id = token['doctor_id']
        patient_id = token['patient_id']
        appointment_date = token['appointment_date']
        status = token['status']
  
        if isinstance(appointment_date, str):
            appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()

        key = (doctor_id, patient_id, appointment_date)
        token_lookup[key] = status


    cursor.close()
    conn.close()

    return render_template(
        "appointment_history.html",
        appointments=appointments,
        token_lookup=token_lookup,
        current_date=date.today()
    )
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE Email = %s", (email,))
        user = cursor.fetchone()

        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['Password'].encode('utf-8')):
            flash("Invalid email or password", "danger")
            return redirect(url_for('login'))

        session['user_id'] = user['User_ID']

        cursor.execute("SELECT p.Patient_ID, p.Name FROM accounts a JOIN patient p ON a.Patient_ID = p.Patient_ID WHERE a.Account_ID = %s", (user['User_ID'],))
        patients = cursor.fetchall()

        conn.close()

        return render_template('select_patient.html', patients=patients)

    return render_template("login.html")

@app.route('/reset_password_verify', methods=['GET'])
def reset_password_verify():
    email = request.args.get('email')

    # Check if email exists in the database
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE Email = %s", (email,))
    user = cursor.fetchone()

    conn.close()

    if user:
        return jsonify({'success': True})  # Proceed with showing the new password form
    else:
        return jsonify({'success': False, 'message': 'Email not found'})


@app.route('/reset_password', methods=['POST'])
def reset_password():
    email = request.form.get('email')
    new_password = request.form.get('newPassword')
    confirm_password = request.form.get('confirmPassword')

    if not new_password or not confirm_password:
        return jsonify({"error": "New password and confirmation are required."}), 400

    # Step 2: Handle password change
    if new_password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    # Hash the new password
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

    # Update the password in the database
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET Password = %s WHERE Email = %s", (hashed_password, email))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Password successfully updated."})

@app.route('/select_patient', methods=['GET', 'POST'])
def select_patient():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    history_mode = request.args.get('mode') == 'history'  # Check if accessed via history

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT p.Patient_ID, p.Name FROM accounts a JOIN patient p ON a.Patient_ID = p.Patient_ID WHERE a.Account_ID = %s", (session['user_id'],))
    patients = cursor.fetchall()
    
    conn.close()
    
    if request.method == 'POST':
        selected_patient_id = request.form.get('patient_id')  # Get selected patient from form
        
        if not selected_patient_id:
            flash("Please select a patient.", "danger")
            return redirect(url_for('select_patient'))

        session['selected_patient_id'] = selected_patient_id  # Store in session
        action = request.form.get('action', '')

        if history_mode:
            return redirect(url_for('appointment_history', patient_id=session['selected_patient_id']))
        elif action == "book":
            return redirect(url_for('doctors', patient_id=session['selected_patient_id']))  
        elif action == "history":
            return redirect(url_for('appointment_history', patient_id=session['selected_patient_id']))
        else:
            flash("Invalid action. Please try again.", "danger")
            return redirect(url_for('select_patient'))

    return render_template('select_patient.html', patients=patients, history_mode=history_mode)

def generate_patient_id():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT MAX(CAST(SUBSTRING(Patient_ID, 4, 3) AS UNSIGNED)) FROM patient")
    last_id = cursor.fetchone()[0]

    new_id = f"AIN{(last_id + 1) if last_id else 1:03d}"
    
    conn.close()
    return new_id


def calculate_age(dob):
    today = datetime.today()
    birth_date = datetime.strptime(dob, "%Y-%m-%d")
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def generate_random_id():
    """Generates a 6-digit random alphanumeric ID (uppercase letters + digits)."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['password']
            name = request.form['name']
            gender = request.form['gender']
            dob = request.form['dob']
            phone = request.form['phone']

            conn = get_db_connection()
            if conn is None:
                flash("Database connection failed!", "danger")
                return redirect(url_for('register'))

            cursor = conn.cursor()

            cursor.execute("SELECT * FROM users WHERE Email = %s", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                flash("Email already exists. Please use a different email.", "danger")
                return redirect(url_for('register'))

            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_id = generate_random_id()

            cursor.execute("INSERT INTO users (User_ID, Email, Password) VALUES (%s, %s, %s)", (user_id, email, hashed_password))

            new_patient_id = generate_patient_id()
            age = calculate_age(dob)

            cursor.execute(
                "INSERT INTO patient (Patient_ID, Name, Gender, DOB, Age, Phone_No) VALUES (%s, %s, %s, %s, %s, %s)",
                (new_patient_id, name, gender, dob, age, phone)
            )

            cursor.execute("INSERT INTO accounts (Account_ID, Patient_ID) VALUES (%s, %s)", (user_id, new_patient_id))

            conn.commit()
            conn.close()

            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            flash(f"Database Error: {str(e)}", "danger")
            return redirect(url_for('register'))

    return render_template('registration.html')

if __name__ == '__main__':
    app.run()
