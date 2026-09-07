from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class KeyRequest(BaseModel):
    url: str
    neg_mark: float = 0.33

@app.post("/calculate")
def calculate_score(data: KeyRequest):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        res = requests.get(data.url, headers=headers, timeout=20)
        soup = BeautifulSoup(res.text, 'html.parser')

        candidate_info = {}
        main_tbl = soup.find('table', border='1') or soup.find('table')
        if main_tbl:
            for row in main_tbl.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 2:
                    k = cols[0].get_text(strip=True)
                    v = cols[1].get_text(strip=True)
                    candidate_info[k] = v

        questions = soup.find_all('div', class_='question-pnl')
        if not questions:
            questions = soup.find_all('div', class_='grp-cntnr')

        attempted = 0
        correct = 0
        wrong = 0

        for q in questions:
            chosen = ""
            for r in q.find_all('tr'):
                txt = r.get_text()
                if "Chosen Option" in txt or "चुना गया विकल्प" in txt:
                    parts = txt.split(":")
                    if len(parts) > 1:
                        chosen = parts[1].strip()

            if chosen and chosen not in ["--", "Not Attempted"] and chosen.isdigit():
                attempted += 1
                right_cell = q.find(class_='rightAns')
                right_opt = ""
                if right_cell:
                    p_row = right_cell.find_parent('tr')
                    if p_row:
                        tds = p_row.find_all('td')
                        if tds:
                            right_opt = tds[0].get_text(strip=True).replace('.', '')

                if chosen == right_opt:
                    correct += 1
                else:
                    wrong += 1

        total_q = len(questions)
        not_attempted = total_q - attempted
        score = (correct * 1.0) - (wrong * data.neg_mark)

        return {
            "status": "success",
            "candidate": candidate_info,
            "total_questions": total_q,
            "attempted": attempted,
            "not_attempted": not_attempted,
            "correct": correct,
            "wrong": wrong,
            "score": round(score, 2)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
