import os
import json
from datetime import datetime
from collections import defaultdict

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify

# Create the Blueprint
assessment_bp = Blueprint('assessment', __name__, url_prefix='/assessment')

# --- Define the headers for your data storage (no longer directly for Google Sheet) ---
# These headers will now serve as a reference for the data structure you'd store locally.
SHEET_HEADERS = [
    "Timestamp", "Name", "Class", "School", "Register Number",
    "Questions Attempted", "Score", "Score Percentage", "Total Questions"
]

# --- Function to simulate data storage (e.g., to a local JSON file) ---
def save_assessment_data_locally(data_row):
    """
    Saves assessment data to a local JSON file.
    In a real application, you might use a database here.
    """
    data_file_path = os.path.join(os.path.dirname(__file__), 'assessment_results.json')
    
    # Ensure the file exists and is a valid JSON array
    if not os.path.exists(data_file_path) or os.path.getsize(data_file_path) == 0:
        with open(data_file_path, 'w', encoding='utf-8') as f:
            json.dump([], f) # Initialize with an empty list

    try:
        with open(data_file_path, 'r+', encoding='utf-8') as f:
            file_data = json.load(f)
            file_data.append(data_row)
            f.seek(0) # Rewind to the beginning of the file
            json.dump(file_data, f, indent=4)
        print(f"Successfully saved data to {data_file_path}")
        return True
    except Exception as e:
        print(f"Error saving data locally: {e}")
        return False

# --- NEW: Function to get leaderboard data ---
def get_leaderboard_data(target_class=None):
    """
    Reads assessment results, calculates the latest score for each student,
    and returns ranked data, optionally filtered by class.
    """
    data_file_path = os.path.join(os.path.dirname(__file__), 'assessment_results.json')
    all_results = []
    if os.path.exists(data_file_path):
        try:
            with open(data_file_path, 'r', encoding='utf-8') as f:
                all_results = json.load(f)
        except json.JSONDecodeError:
            print("Error decoding JSON from assessment_results.json. File might be empty or corrupt.")
            return {} # Return empty if file is invalid JSON

    # Use defaultdict to store the latest score for each unique student (name + reg_number + class)
    # This assumes the latest entry for a student represents their current score.
    latest_scores = defaultdict(lambda: {'score': -1, 'timestamp': datetime.min, 'data': None})

    for entry in all_results:
        try:
            name = entry.get('Name')
            student_class = str(entry.get('Class')) # Ensure class is string for consistent key
            reg_number = entry.get('Register Number')
            score = int(entry.get('Score', 0))
            timestamp_str = entry.get('Timestamp')
            
            # Create a unique identifier for the student within their class
            student_id = f"{name}-{reg_number}-{student_class}"

            # Convert timestamp to datetime object for comparison
            entry_timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

            # Update if this is a newer submission for this student_id
            if entry_timestamp > latest_scores[student_id]['timestamp']:
                latest_scores[student_id]['score'] = score
                latest_scores[student_id]['timestamp'] = entry_timestamp
                latest_scores[student_id]['data'] = entry

        except (ValueError, TypeError, KeyError) as e:
            print(f"Skipping malformed entry in assessment_results.json: {entry} Error: {e}")
            continue
            
    # Group results by class
    leaderboards_by_class = defaultdict(list)
    for student_id, data_entry in latest_scores.items():
        entry_data = data_entry['data']
        class_num = str(entry_data.get('Class')) # Ensure consistent string
        leaderboards_by_class[class_num].append(entry_data)
    
    # Sort each class leaderboard
    for class_num in leaderboards_by_class:
        leaderboards_by_class[class_num].sort(key=lambda x: int(x.get('Score', 0)), reverse=True)

    # If a target_class is specified, return only that leaderboard
    if target_class:
        return {target_class: leaderboards_by_class.get(str(target_class), [])}
    
    return dict(leaderboards_by_class) # Convert back to dict for general use

# --- This route is correct and does not need changes ---
@assessment_bp.route('/take', methods=['GET', 'POST'])
def take_assessment():
    if request.method == 'POST':
        session['student_details'] = {
            "name": request.form.get('name'),
            "class": request.form.get('class'),
            "school": request.form.get('school'),
            "register_number": request.form.get('register_number', '')
        }
        flash('Student details saved temporarily. Please review the rules before starting.', 'success')
        return redirect(url_for('assessment.show_rules'))
        
    return render_template('assessment_form.html')

# --- This route is correct and does not need changes ---
@assessment_bp.route('/rules')
def show_rules():
    return render_template('rules.html')

# --- This route is correct and does not need changes ---
@assessment_bp.route('/test')
def start_test():
    if 'student_details' not in session:
        flash('Please enter your details before starting the test.', 'info')
        return redirect(url_for('assessment.take_assessment'))
    
    selected_class = session['student_details'].get('class')
    if not selected_class:
        flash('Class information is missing. Please re-enter your details.', 'danger')
        return redirect(url_for('assessment.take_assessment'))

    try:
        file_path = os.path.join(os.path.dirname(__file__), 'test_questions.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            all_questions_data = json.load(f)

        return render_template('test.html', test_questions=all_questions_data, selected_class=selected_class)
    except FileNotFoundError:
        flash('The test questions could not be loaded. Please contact an administrator.', 'danger')
        return redirect(url_for('home'))
    except KeyError:
        flash(f'No questions found for class {selected_class}. Please check the class or contact an administrator.', 'danger')
        return redirect(url_for('assessment.take_assessment'))

# --- UPDATED: This function now saves data locally and passes results to thank_you page ---
@assessment_bp.route('/submit', methods=['POST'])
def submit_test():
    """Evaluates text answers, retrieves details from session, and saves data locally."""
    
    print("--- SUBMIT TEST ROUTE TRIGGERED ---")
    print("Session data upon submission:", session)

    user_answers = request.form
    score = 0
    
    if 'student_details' not in session:
        flash('Your session expired. Please enter your details again.', 'warning')
        return redirect(url_for('assessment.take_assessment'))

    selected_class = session['student_details'].get('class')
    if not selected_class:
        flash('Class information is missing. Cannot submit test.', 'danger')
        return redirect(url_for('assessment.take_assessment'))

    try:
        file_path = os.path.join(os.path.dirname(__file__), 'test_questions.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            all_questions_data = json.load(f)
        
        class_questions = all_questions_data.get(selected_class, [])
        if not class_questions:
            flash(f'No questions found for class {selected_class} to evaluate. Contact administrator.', 'danger')
            return redirect(url_for('assessment.take_assessment'))

        total_questions = len(class_questions)
        correct_answers_dict = {str(q['id']): q['answer'] for q in class_questions}
        
        questions_attempted = 0
        for q_id, correct_ans in correct_answers_dict.items():
            user_ans = user_answers.get(f'question_{q_id}')
            
            if user_ans and user_ans.strip() != '':
                questions_attempted += 1
                if user_ans.strip().lower() == correct_ans.strip().lower():
                    score += 1

        student_details = session.pop('student_details')
        score_percentage = f"{(score / total_questions) * 100:.0f}%" if total_questions > 0 else "0%"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create a dictionary mapping headers to values
        data_to_save = {
            "Timestamp": timestamp,
            "Name": student_details.get('name', ''),
            "Class": student_details.get('class', ''),
            "School": student_details.get('school', ''),
            "Register Number": student_details.get('register_number', ''),
            "Questions Attempted": questions_attempted,
            "Score": score,
            "Score Percentage": score_percentage,
            "Total Questions": total_questions # ADDED THIS LINE TO SAVE TOTAL QUESTIONS
        }
        
        print("Data prepared for local saving:")
        for header, value in data_to_save.items():
            print(f"    {header}: {value}")

        print("Attempting to save data locally...")
        if save_assessment_data_locally(data_to_save):
            print("Successfully saved data locally.")
            flash('Your test has been submitted successfully!', 'success')
            
            # Store the results in session to pass to the thank_you page
            session['test_results'] = {
                'score': score,
                'total_questions': total_questions,
                'score_percentage': score_percentage,
                'name': student_details.get('name', ''),
                'class': selected_class # Also store the class here for leaderboard filtering
            }
            
            return redirect(url_for('assessment.thank_you'))
        else:
            raise Exception("Failed to save data locally.")

    except Exception as e:
        print(f"An error occurred during submission: {e}")
        import traceback
        traceback.print_exc()
        flash('Could not submit results due to a server error. Please try again.', 'danger')
        return redirect(url_for('assessment.start_test'))

# --- UPDATED: Pass results and leaderboard to thank.html ---
@assessment_bp.route('/thank_you')
def thank_you():
    results = session.pop('test_results', None) # Retrieve and clear results from session
    
    # Initialize leaderboard_data as empty
    leaderboard_data = {} 
    
    if results:
        # Get leaderboard for the student's class
        student_class = results.get('class')
        if student_class:
            leaderboard_data = get_leaderboard_data(target_class=student_class)
        return render_template('thank.html', results=results, leaderboard=leaderboard_data)
    else:
        # If results aren't in session (e.g., direct access), redirect to take assessment
        flash('No results to display. Please take the assessment first.', 'info')
        return redirect(url_for('assessment.take_assessment'))

# --- NEW: Route to view all leaderboards (optional, for admin/separate page) ---
@assessment_bp.route('/leaderboards')
def view_leaderboards():
    all_leaderboards = get_leaderboard_data() # Get all classes' leaderboards
    return render_template('leaderboards_overview.html', all_leaderboards=all_leaderboards)

# --- NEW: Route for specific class leaderboard (optional, if using dropdown) ---
@assessment_bp.route('/leaderboard/<int:class_id>')
def class_leaderboard(class_id):
    leaderboard = get_leaderboard_data(target_class=str(class_id))
    if not leaderboard:
        flash(f'No data available for Class {class_id}.', 'info')
        return redirect(url_for('assessment.view_leaderboards')) # Or a general thank you
    return render_template('leaderboards_overview.html', all_leaderboards=leaderboard, current_class=class_id) # Use same template, pass specific class

# --- NEW: Route for Teacher Dashboard to view all class leaderboards ---
@assessment_bp.route('/teacher_dashboard')
def teacher_dashboard():
    all_leaderboards = get_leaderboard_data() # Get leaderboards for all classes
    return render_template('teacher_dashboard.html', leaderboard_data=all_leaderboards)

# --- NEW: Route to delete all assessment results (for the delete button) ---
@assessment_bp.route('/delete_all_results', methods=['POST'])
def delete_all_results():
    """Deletes the local assessment_results.json file."""
    # NOTE: In a real-world app, you would add a check here to ensure the user is an admin or teacher.
    # For now, anyone with access to the dashboard can trigger this.
    data_file_path = os.path.join(os.path.dirname(__file__), 'assessment_results.json')
    
    if os.path.exists(data_file_path):
        try:
            os.remove(data_file_path)
            flash('All assessment data has been successfully deleted.', 'success')
            print("Successfully deleted assessment_results.json")
        except OSError as e:
            flash(f'Error deleting data file: {e}', 'danger')
            print(f"Error deleting data file: {e}")
    else:
        flash('No data file found to delete.', 'info')

    return redirect(url_for('assessment.teacher_dashboard'))
