from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pandas as pd
import sqlite3
import os
import random

app = Flask(__name__)
app.secret_key = 'super_secret_key' # 세션 관리를 위한 비밀 키

DATABASE = 'database.db'
QUIZ_FILE = 'quiz.xlsx'

# 데이터베이스 연결
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# 데이터베이스 초기화
def init_db():
    conn = get_db()
    with open('schema.sql', 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

# 사용자 등록 (초기 사용자 홍길동, 1111)
def add_initial_user():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", ('홍길동',))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('홍길동', '1111'))
        conn.commit()
    conn.close()

# 퀴즈 데이터 로드
def load_quiz_data():
    try:
        df = pd.read_excel(QUIZ_FILE)
        # 컬럼명 확인 및 변경 (혹시 모를 대소문자 문제 방지)
        df.columns = [col.lower() for col in df.columns]
        required_columns = ['문제', '보기a', '보기b', '보기c', '보기d', '정답', '해설']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"quiz.xlsx 파일에 필요한 컬럼이 모두 없습니다: {required_columns}")
        
        # 보기 항목에서 'a.', 'b.' 등의 접두사 제거
        for col in ['보기a', '보기b', '보기c', '보기d']:
            if col in df.columns:
                df[col] = df[col].astype(str).apply(lambda x: x[x.find('.')+1:].strip() if x.strip().lower().startswith(('a.', 'b.', 'c.', 'd.')) else x)

        return df.to_dict(orient='records')
    except Exception as e:
        print(f"Error loading quiz data: {e}")
        return []

quiz_data = load_quiz_data()

@app.before_request
def before_request():
    if 'user_id' not in session and request.endpoint != 'login' and request.endpoint != 'static':
        if request.endpoint is not None:
            return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('quiz'))
        else:
            flash('잘못된 사용자 이름 또는 비밀번호입니다.', 'danger')
    return render_template('login.html')

@app.route('/quiz')
def quiz():
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'danger')
        return redirect(url_for('login'))
    
    if 'current_quiz_index' not in session:
        session['current_quiz_index'] = 0
        session['quiz_order'] = random.sample(range(len(quiz_data)), min(5, len(quiz_data))) # 최대 5문제
        session['user_answers'] = [None] * len(session['quiz_order'])
    
    current_index = session['current_quiz_index']
    quiz_order = session['quiz_order']

    if current_index >= len(quiz_order):
        return redirect(url_for('result'))
    
    question_idx = quiz_order[current_index]
    question = quiz_data[question_idx].copy() # Make a copy to modify

    # Split the question into Korean instruction and English sentence
    question_text = question['문제']
    korean_instruction = ""
    english_sentence = ""

    # Simple heuristic to split: find the first English alphabet character
    first_english_char_idx = -1
    for i, char in enumerate(question_text):
        if 'a' <= char.lower() <= 'z':
            first_english_char_idx = i
            break

    if first_english_char_idx != -1:
        korean_instruction = question_text[:first_english_char_idx].strip()
        english_sentence = question_text[first_english_char_idx:].strip()
    else:
        korean_instruction = question_text
        english_sentence = "" # No English sentence found, or it's purely Korean.
    
    question['korean_instruction'] = korean_instruction
    question['english_sentence'] = english_sentence
    
    return render_template('quiz.html', question=question, question_num=current_index + 1, total_questions=len(quiz_order))

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'danger')
        return redirect(url_for('login'))
    
    try:
        current_index = session.get('current_quiz_index', 0)
        quiz_order = session.get('quiz_order', [])
        
        if current_index >= len(quiz_order):
            return redirect(url_for('result'))

        selected_answer = request.form.get('answer')
        
        if selected_answer is None:
            flash('답변을 선택해주세요.', 'warning')
            question_idx = quiz_order[current_index]
            question = quiz_data[question_idx]
            return render_template('quiz.html', question=question, question_num=current_index + 1, total_questions=len(quiz_order))

        session['user_answers'][current_index] = selected_answer
        session['current_quiz_index'] += 1
        session.modified = True # 세션 변경사항 저장

        return redirect(url_for('quiz'))
    except Exception as e:
        flash(f'답변 제출 중 오류가 발생했습니다: {e}', 'danger')
        return redirect(url_for('quiz'))

@app.route('/result')
def result():
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'danger')
        return redirect(url_for('login'))
    
    if 'quiz_order' not in session or 'user_answers' not in session:
        flash('퀴즈 기록이 없습니다. 다시 시작해주세요.', 'warning')
        return redirect(url_for('quiz'))

    quiz_order = session['quiz_order']
    user_answers = session['user_answers']
    
    results = []
    score = 0
    letter_to_num_map = {'a': '1', 'b': '2', 'c': '3', 'd': '4'}

    for i, q_idx in enumerate(quiz_order):
        question = quiz_data[q_idx]
        
        user_selected_num = user_answers[i] # This is the user's choice as 1, 2, 3, or 4 (or None)

        correct_answer_raw = str(question['정답']).strip().lower()
        
        # This map converts both letter answers and direct number answers to a consistent numeric string format.
        answer_mapping = {
            'a': '1', 'b': '2', 'c': '3', 'd': '4',
            '1': '1', '2': '2', '3': '3', '4': '4'
        }

        # Try to parse the correct answer from the raw string.
        # It could be 'a', '1', 'a. Some text', '1. Some text'.
        correct_answer_parsed_for_comparison = None
        if correct_answer_raw:
            first_char = correct_answer_raw[0]
            if first_char in answer_mapping:
                correct_answer_parsed_for_comparison = answer_mapping[first_char]

        # Now, correct_answer_parsed_for_comparison will be '1', '2', '3', '4' or None
        # This is the value we'll use for comparison and display.
        correct_answer_display_value = correct_answer_parsed_for_comparison

        # Compare user's selected number (as string) with the parsed correct answer number (as string)
        is_correct = (str(user_selected_num) == correct_answer_display_value) if user_selected_num and correct_answer_display_value else False

        if is_correct:
            score += 1

        # For displaying selected answer (user_selected_num is already a number)
        selected_answer_display = str(user_selected_num) if user_selected_num else '선택 안 함'
        
        results.append({
            'question_num': i + 1,
            'original_quiz_index': q_idx,
            'question_text': question['문제'],
            'selected_answer': selected_answer_display,
            'correct_answer': correct_answer_raw, # Internal for logic (original raw value)
            'correct_answer_display': correct_answer_display_value, # For displaying correct answer as number (e.g., '3')
            'explanation': question['해설'],
            'is_correct': is_correct
        })
    
    total_questions = len(quiz_order)
    
    # 세션 초기화 (퀴즈 재시작을 위해)
    session.pop('current_quiz_index', None)
    session.pop('quiz_order', None)
    session.pop('user_answers', None)

    return render_template('result.html', results=results, score=score, total_questions=total_questions)

@app.route('/review_question/<int:original_quiz_index>')
def review_question(original_quiz_index):
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'danger')
        return redirect(url_for('login'))

    if not (0 <= original_quiz_index < len(quiz_data)):
        flash('유효하지 않은 문제 번호입니다.', 'danger')
        return redirect(url_for('result'))

    question = quiz_data[original_quiz_index]

    correct_answer_raw = str(question['정답']).strip().lower()

    # This map converts both letter answers and direct number answers to a consistent numeric string format.
    answer_mapping = {
        'a': '1', 'b': '2', 'c': '3', 'd': '4',
        '1': '1', '2': '2', '3': '3', '4': '4'
    }

    # Try to parse the correct answer from the raw string.
    # It could be 'a', '1', 'a. Some text', '1. Some text'.
    correct_answer_parsed_for_display = None
    if correct_answer_raw:
        first_char = correct_answer_raw[0]
        if first_char in answer_mapping:
            correct_answer_parsed_for_display = answer_mapping[first_char]

    # correct_answer_display will be '1', '2', '3', '4' or None
    correct_answer_display = correct_answer_parsed_for_display
    
    return render_template('review_question.html', question=question, original_quiz_index=original_quiz_index, correct_answer_display=correct_answer_display)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('current_quiz_index', None)
    session.pop('quiz_order', None)
    session.pop('user_answers', None)
    flash('로그아웃 되었습니다.', 'info')
    return redirect(url_for('login'))

@app.route('/download_results_json')
def download_results_json():
    if 'user_id' not in session:
        return jsonify({'error': '로그인이 필요합니다.'}), 401
    
    # 결과 데이터를 다시 계산 (세션에 저장된 user_answers와 quiz_order를 기반으로)
    quiz_order = session.get('quiz_order', [])
    user_answers = session.get('user_answers', [])

    if not quiz_order or not user_answers:
        return jsonify({'error': '퀴즈 기록이 없습니다.'}), 400

    results_data = []
    letter_to_num_map = {'a': '1', 'b': '2', 'c': '3', 'd': '4'}

    for i, q_idx in enumerate(quiz_order):
        question = quiz_data[q_idx]
        user_selected_num = user_answers[i]

        correct_answer_from_excel_letter = str(question['정답']).lower().strip()
        correct_answer_num_for_display = letter_to_num_map.get(correct_answer_from_excel_letter, correct_answer_from_excel_letter)

        # For display in JSON: convert user's selected number to string
        selected_answer_display = str(user_selected_num) if user_selected_num else '선택 안 함'

        results_data.append({
            'question_num': i + 1,
            'question_text': question['문제'],
            'selected_answer': selected_answer_display,
            'correct_answer': correct_answer_num_for_display,
            'explanation': question['해설'],
        })

    return jsonify(results_data)

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
        add_initial_user()
    app.run(debug=True)
