import os
import json
from datetime import datetime

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify

# Create the Blueprint
assessment_bp = Blueprint('assessment', __name__, url_prefix='/assessment')

# --- Define the headers for your data storage (no longer directly for Google Sheet) ---
# These headers will now serve as a reference for the data structure you'd store locally.
SHEET_HEADERS = [
    "Timestamp", "Name", "Class", "School", "Register Number",
    "Questions Attempted", "Score", "Score Percentage"
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
            f.seek(0)  # Rewind to the beginning of the file
            json.dump(file_data, f, indent=4)
        print(f"Successfully saved data to {data_file_path}")
        return True
    except Exception as e:
        print(f"Error saving data locally: {e}")
        return False


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
            "Score Percentage": score_percentage
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
                'name': student_details.get('name', '')
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

# --- UPDATED: Pass results to thank.html ---
@assessment_bp.route('/thank_you')
def thank_you():
    results = session.pop('test_results', None) # Retrieve and clear results from session
    if results:
        return render_template('thank.html', results=results)
    else:
        # If results aren't in session (e.g., direct access), redirect to take assessment
        flash('No results to display. Please take the assessment first.', 'info')
        return redirect(url_for('assessment.take_assessment'))

# --- Optional: Removed admin/reset-headers as it was Google Sheets specific ---