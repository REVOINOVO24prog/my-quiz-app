import os
import re
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# File path to persist application data locally
DATA_FILE = 'quiz_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'sections': {}, 'stats': {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def parse_txt_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into raw question blocks
    blocks = re.split(r'\n(?=Question\s+\d+)', content.strip())
    parsed_questions = []

    for block in blocks:
        if not block.strip():
            continue
        
        # Extract question header and text
        q_match = re.search(r'Question\s+(\d+)[\:\s]*(.*?)(?=\n[A-D]\.|\nAnswer:|\n\||\nColumn|\Z)', block, re.DOTALL | re.IGNORECASE)
        q_num = q_match.group(1) if q_match else ""
        q_text = q_match.group(2).strip() if q_match else block.split('\n')[0]

        # Extract Options A, B, C, D
        options = re.findall(r'([A-D])\.\s*(.*?)(?=\n[A-D]\.|\nAnswer:|\n\||\nColumn|\Z)', block, re.DOTALL)
        options_dict = {opt[0].upper(): opt[1].strip() for opt in options}

        # Extract Answer
        ans_match = re.search(r'Answer:\s*([A-D])', block, re.IGNORECASE)
        answer = ans_match.group(1).upper() if ans_match else ""

        # Extract Table / Side-by-Side Column Data
        table_html = ""
        table_lines = [line.strip() for line in block.split('\n') if line.strip().startswith('|') or 'Column' in line or re.match(r'^\d+\.\s+192\.', line.strip()) or re.match(r'^[a-d]\)', line.strip())]
        
        if table_lines:
            table_html = "<div class='parsed-table-container'><pre>" + "\n".join(table_lines) + "</pre></div>"

        parsed_questions.append({
            'num': q_num,
            'question': q_text,
            'options': options_dict,
            'answer': answer,
            'table': table_html
        })

    # Divide into up to 36 sections holding 30 questions each
    sections = {}
    for i in range(36):
        section_id = str(i + 1)
        start_idx = i * 30
        end_idx = start_idx + 30
        sec_qs = parsed_questions[start_idx:end_idx]
        
        sections[section_id] = sec_qs

    return sections

@app.route('/')
def index():
    return redirect(url_for('upload'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file selected", 400
        file = request.files['file']
        if file.filename == '':
            return "No file selected", 400
        
        path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(path)

        sections = parse_txt_file(path)
        
        # Save parsed data to persistent json file
        data = load_data()
        data['sections'] = sections
        
        # Initialize stats for 36 sections
        if 'stats' not in data:
            data['stats'] = {}
            
        for sec_id in range(1, 37):
            s_str = str(sec_id)
            if s_str not in data['stats']:
                data['stats'][s_str] = {
                    'opened_count': 0,
                    'full_attempts': 0,
                    'last_attempt_progress': 0
                }

        save_data(data)
        return redirect(url_for('dashboard'))

    return render_template('upload.html')

@app.route('/dashboard')
def dashboard():
    data = load_data()
    sections = data.get('sections', {})
    stats = data.get('stats', {})
    return render_template('dashboard.html', sections=sections, stats=stats)

@app.route('/quiz/<section_id>')
def quiz(section_id):
    data = load_data()
    
    # Increment times opened counter
    if section_id in data.get('stats', {}):
        data['stats'][section_id]['opened_count'] += 1
        save_data(data)

    questions = data.get('sections', {}).get(section_id, [])
    return render_template('quiz.html', section_id=section_id, questions=questions)

@app.route('/api/submit_quiz', methods=['POST'])
def submit_quiz():
    payload = request.json
    section_id = str(payload.get('section_id'))
    progress = payload.get('progress', 0)
    is_completed = payload.get('completed', False)

    data = load_data()
    if section_id in data.get('stats', {}):
        data['stats'][section_id]['last_attempt_progress'] = progress
        if is_completed:
            data['stats'][section_id]['full_attempts'] += 1
        save_data(data)

    return jsonify({'status': 'success'})

@app.route('/api/reset', methods=['POST'])
def reset_app():
    # Delete persisted database file
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)

    # Clean uploads directory
    folder = app.config['UPLOAD_FOLDER']
    if os.path.exists(folder):
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)