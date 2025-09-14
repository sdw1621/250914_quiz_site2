# 퀴즈 웹사이트

이 프로젝트는 Python Flask를 사용하여 학생들을 위한 간단한 퀴즈 웹사이트를 구현합니다.

## 주요 기능

*   사용자 로그인 (SQLite)
*   `quiz.xlsx` 파일에서 무작위 5문제 출제
*   Card News 형식의 문제 표시
*   Bootstrap을 이용한 현대적인 UI
*   결과 페이지 및 문제 다시 보기 기능

## 설치 및 실행 방법

1.  **가상 환경 설정:**

    ```bash
    python -m venv quiz_venv
    .\quiz_venv\Scripts\activate
    ```

2.  **의존성 설치:**

    ```bash
    pip install Flask pandas openpyxl
    ```

3.  **애플리케이션 실행:**

    ```bash
    python app.py
    ```

4.  **브라우저에서 접속:**

    `http://127.0.0.1:5000` 으로 접속합니다.

## 초기 사용자

*   **사용자 이름:** 홍길동
*   **비밀번호:** 1111

## 퀴즈 데이터 형식

`quiz.xlsx` 파일은 다음 컬럼을 포함해야 합니다:

`문제`, `보기a`, `보기b`, `보기c`, `보기d`, `정답`, `해설`
