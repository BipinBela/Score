from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re

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
        res = requests.get(data.url, headers=headers, timeout=25)
        soup = BeautifulSoup(res.text, 'html.parser')

        # 1. Candidate Info
        candidate_info = {}
        for row in soup.find_all('tr'):
            tds = row.find_all('td')
            if len(tds) == 2:
                k = tds[0].get_text(strip=True)
                v = tds[1].get_text(strip=True)
                if any(x in k for x in ["Roll", "Name", "Subject", "Date", "Center", "Community", "Registration"]):
                    candidate_info[k] = v

        # 2. All questions panels
        questions = soup.find_all('div', class_=re.compile(r'(question-pnl|grp-cntnr|section-cntnr)'))
        if not questions:
            # वैकल्पिक तरीका अगर div क्लास न मिले
            questions = [tbl.find_parent('div') for tbl in soup.find_all('table', class_=re.compile(r'menu-tbl'))]
            questions = [q for q in questions if q is not None]

        total_q = len(questions)
        attempted = 0
        correct = 0
        wrong = 0

        for q in questions:
            chosen = ""
            # Chosen option खोजना
            for td in q.find_all(['td', 'span', 'b']):
                text = td.get_text(strip=True)
                if "Chosen Option" in text or "चुना गया विकल्प" in text:
                    parts = text.split(":")
                    if len(parts) > 1:
                        chosen = parts[1].strip()
                    else:
                        next_sib = td.find_next_sibling()
                        if next_sib:
                            chosen = next_sib.get_text(strip=True)

            # Right Option खोजना
            right_opt = ""
            right_ans_elem = q.find(class_=re.compile(r'rightAns'))
            if right_ans_elem:
                parent_row = right_ans_elem.find_parent('tr')
                if parent_row:
                    cells = parent_row.find_all('td')
                    if cells:
                        raw_num = cells[0].get_text(strip=True)
                        m = re.search(r'\d+', raw_num)
                        if m:
                            right_opt = m.group()

            # Attempted check
            if chosen and chosen not in ["--", "Not Attempted"] and chosen.isdigit():
                attempted += 1
                if chosen == right_opt:
                    correct += 1
                else:
                    wrong += 1

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
