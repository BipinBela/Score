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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8'
    }
    try:
        req_url = data.url.strip()
        # डबल स्लैश को ठीक करना
        if "://" in req_url:
            prot, rest = req_url.split("://", 1)
            rest = re.sub(r'/+', '/', rest)
            req_url = f"{prot}://{rest}"

        res = requests.get(req_url, headers=headers, timeout=30)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        # 1. कैंडिडेट विवरण
        candidate_info = {}
        for row in soup.find_all('tr'):
            tds = row.find_all('td')
            if len(tds) == 2:
                k = tds[0].get_text(strip=True)
                v = tds[1].get_text(strip=True)
                if any(x in k for x in ["Roll", "Name", "Subject", "Date", "Center", "Community", "Registration", "अनुक्रमांक", "नाम"]):
                    candidate_info[k] = v

        # 2. प्रश्न खोजना
        menu_tables = soup.find_all('table', class_=re.compile(r'menu-tbl|questionRowTbl', re.I))
        
        # अगर क्लास से न मिले तो 'Chosen Option' वाले टेबल खोजना
        if not menu_tables:
            for tbl in soup.find_all('table'):
                if "Chosen Option" in tbl.get_text() or "चुना गया विकल्प" in tbl.get_text():
                    menu_tables.append(tbl)

        total_q = len(menu_tables)
        attempted = 0
        correct = 0
        wrong = 0

        for menu in menu_tables:
            # पैरेंट कंटेनर
            q_box = menu.find_parent('div', class_=re.compile(r'question-pnl|grp-cntnr|section-cntnr')) or menu.find_parent('table') or menu.parent

            # 1. कैंडिडेट का चुना गया विकल्प
            chosen = ""
            for tr in menu.find_all('tr'):
                txt = tr.get_text()
                if "Chosen Option" in txt or "चुना गया विकल्प" in txt:
                    parts = txt.split(":")
                    if len(parts) > 1:
                        chosen = parts[1].strip()

            # 2. सही उत्तर (TCS iON tick image या rightAns)
            right_opt = ""
            # तरीका A: rightAns क्लास
            right_td = q_box.find(class_=re.compile(r'rightAns', re.I))
            if right_td:
                p_row = right_td.find_parent('tr')
                if p_row:
                    first_col = p_row.find('td')
                    if first_col:
                        m = re.search(r'\d+', first_col.get_text())
                        if m:
                            right_opt = m.group()

            # तरीका B: img src जिसमें tick या right हो
            if not right_opt:
                tick_img = q_box.find('img', src=re.compile(r'tick|correct|right', re.I))
                if tick_img:
                    p_row = tick_img.find_parent('tr')
                    if p_row:
                        first_col = p_row.find('td')
                        if first_col:
                            m = re.search(r'\d+', first_col.get_text())
                            if m:
                                right_opt = m.group()

            # 3. स्कोर गणना
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
