"""
데이터 정합성 검사 및 정제 (Sanitize)
- 미래 날짜 수정
- 빈 rating 필드 보정
- 날짜 기준 정렬
"""
import os
import sys
import datetime
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_db, save_db, logger


def sanitize():
    logger.info("=== 02_Store: 데이터 정합성 검사 (Sanitize) 시작 ===")
    db = load_db()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    fixed_dates = 0
    fixed_ratings = 0

    # 1. 미래 날짜 수정 (reports)
    for rep in db.get("reports", []):
        d = rep.get("date", "")
        if d and d > today:
            rep["date"] = today
            fixed_dates += 1

    # 2. 미래 날짜 수정 (recommendations)
    for rec in db.get("recommendations", []):
        d = rec.get("date", "")
        if d and d > today:
            rec["date"] = today
            fixed_dates += 1

    # 3. 빈 rating 필드 보정
    for rep in db.get("reports", []):
        if not rep.get("rating"):
            rep["rating"] = "매수 (Buy)"
            fixed_ratings += 1

    # 4. 날짜 내림차순 정렬
    db["reports"] = sorted(
        db.get("reports", []),
        key=lambda x: x.get("date", ""),
        reverse=True
    )
    db["recommendations"] = sorted(
        db.get("recommendations", []),
        key=lambda x: x.get("date", ""),
        reverse=True
    )

    save_db(db)
    logger.info(
        f"=== Sanitize 완료: 미래 날짜 {fixed_dates}건 수정, "
        f"빈 등급 {fixed_ratings}건 보정 ==="
    )


if __name__ == "__main__":
    sanitize()
