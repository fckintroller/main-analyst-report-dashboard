"""
NAVER DataLab 수집 스크립트 — 한국 주식 테마/섹터 검색 관심도.

- 소스: NAVER DataLab Search API
- 인증: 프로젝트 루트 .env의 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
- 저장 경로: data/raw/sentiment/naver_datalab/
- 실행:
    python scripts/01_collect/collect_naver_datalab_once.py
    python scripts/01_collect/collect_naver_datalab_once.py --universe sector --time-unit month --start-date 2021-01-01 --end-date 2026-06-05

주의:
- NAVER DataLab ratio는 절대 검색량이 아니라 요청 범위/그룹 내 상대 지수입니다.
- sector universe는 요청마다 market_anchor를 포함해 anchor 대비 상대강도 팩터를 별도로 저장합니다.
- 키 원문은 로그에 출력하지 않습니다.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SAVE_DIR = PROJECT_ROOT / "data" / "raw" / "sentiment" / "naver_datalab"
API_URL = "https://openapi.naver.com/v1/datalab/search"
ANCHOR_GROUP_NAME = "market_anchor"
ANCHOR_KEYWORD_GROUP = {"groupName": ANCHOR_GROUP_NAME, "keywords": ["코스피", "코스닥", "주식"]}

# groupName은 ASCII slug로 둔다. 한글명은 keywords에 보존된다.
DEFAULT_KEYWORD_GROUPS = [
    {"groupName": "battery_theme", "keywords": ["2차전지", "배터리", "전고체배터리"]},
    {"groupName": "power_grid_theme", "keywords": ["전력", "송전망", "전력기기"]},
    {"groupName": "renewable_theme", "keywords": ["신재생에너지", "태양광", "풍력"]},
    {"groupName": "defense_theme", "keywords": ["방산", "방위산업", "K방산"]},
    {"groupName": "semiconductor_theme", "keywords": ["반도체", "HBM", "AI반도체"]},
    {"groupName": "market_index", "keywords": ["코스피", "코스닥", "주식"]},
]

SECTOR_KEYWORD_GROUPS = [
    {"groupName": "semiconductor", "keywords": ["반도체", "HBM", "메모리반도체", "시스템반도체"]},
    {"groupName": "battery", "keywords": ["2차전지", "배터리", "전고체배터리", "양극재"]},
    {"groupName": "auto", "keywords": ["자동차", "전기차", "현대차", "자동차부품"]},
    {"groupName": "shipbuilding", "keywords": ["조선", "선박", "LNG선", "조선주"]},
    {"groupName": "steel", "keywords": ["철강", "철강주", "후판", "포스코"]},
    {"groupName": "chemical", "keywords": ["화학", "석유화학", "화학주"]},
    {"groupName": "refinery", "keywords": ["정유", "유가", "정유주"]},
    {"groupName": "construction", "keywords": ["건설", "건설주", "부동산개발"]},
    {"groupName": "bank", "keywords": ["은행", "은행주", "금융지주"]},
    {"groupName": "securities", "keywords": ["증권", "증권주", "브로커리지"]},
    {"groupName": "insurance", "keywords": ["보험", "보험주", "손해보험", "생명보험"]},
    {"groupName": "internet", "keywords": ["인터넷", "플랫폼", "네이버", "카카오"]},
    {"groupName": "game", "keywords": ["게임", "게임주", "모바일게임"]},
    {"groupName": "media_entertainment", "keywords": ["엔터", "미디어", "K팝", "콘텐츠"]},
    {"groupName": "bio_pharma", "keywords": ["바이오", "제약", "신약", "제약주"]},
    {"groupName": "medical_device", "keywords": ["의료기기", "미용기기", "헬스케어"]},
    {"groupName": "food_beverage", "keywords": ["음식료", "식품", "라면", "주류"]},
    {"groupName": "retail", "keywords": ["유통", "백화점", "편의점", "이커머스"]},
    {"groupName": "cosmetics", "keywords": ["화장품", "K뷰티", "화장품주"]},
    {"groupName": "apparel", "keywords": ["의류", "패션", "섬유"]},
    {"groupName": "telecom", "keywords": ["통신", "통신주", "5G"]},
    {"groupName": "utility_power", "keywords": ["전력", "유틸리티", "전기요금"]},
    {"groupName": "machinery", "keywords": ["기계", "산업기계", "건설기계"]},
    {"groupName": "defense", "keywords": ["방산", "방위산업", "K방산"]},
    {"groupName": "airline_transport", "keywords": ["항공", "운송", "물류"]},
    {"groupName": "shipping", "keywords": ["해운", "해운주", "운임"]},
    {"groupName": "display", "keywords": ["디스플레이", "OLED", "LCD"]},
    {"groupName": "it_parts", "keywords": ["IT부품", "스마트폰부품", "카메라모듈"]},
    {"groupName": "power_equipment", "keywords": ["전력기기", "변압기", "송전망"]},
    {"groupName": "robot", "keywords": ["로봇", "산업용로봇", "휴머노이드"]},
    {"groupName": "ai_software", "keywords": ["AI", "인공지능", "소프트웨어"]},
    {"groupName": "nuclear", "keywords": ["원전", "원자력", "SMR"]},
    {"groupName": "renewable", "keywords": ["신재생에너지", "태양광", "풍력"]},
    {"groupName": "holding_company", "keywords": ["지주사", "지주회사"]},
    {"groupName": "reit_realestate", "keywords": ["리츠", "부동산", "임대"]},
]


def default_start_date(today: date | None = None) -> str:
    """기본 수집 시작일: 오늘 기준 약 5년 전."""
    today = today or date.today()
    return (today - timedelta(days=365 * 5)).isoformat()


def get_keyword_groups(universe: str = "theme") -> list[dict[str, list[str] | str]]:
    if universe == "theme":
        return list(DEFAULT_KEYWORD_GROUPS)
    if universe == "sector":
        return list(SECTOR_KEYWORD_GROUPS)
    raise ValueError("universe must be one of: theme, sector")


def build_payload(
    keyword_groups: list[dict[str, list[str] | str]],
    start_date: str,
    end_date: str,
    time_unit: str = "month",
) -> dict:
    if time_unit not in {"date", "week", "month"}:
        raise ValueError("time_unit must be one of: date, week, month")
    return {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "keywordGroups": keyword_groups,
    }


def parse_response_to_frame(payload: dict) -> pd.DataFrame:
    rows = []
    for group in payload.get("results", []) or []:
        group_name = group.get("title", "")
        keywords = "|".join(str(x) for x in group.get("keywords", []) or [])
        for point in group.get("data", []) or []:
            rows.append(
                {
                    "period": point.get("period"),
                    "group_name": group_name,
                    "keywords": keywords,
                    "ratio": float(point.get("ratio", 0.0)),
                }
            )
    df = pd.DataFrame(rows, columns=["period", "group_name", "keywords", "ratio"])
    if not df.empty:
        df = df.sort_values(["group_name", "period"]).reset_index(drop=True)
    return df


def chunk_keyword_groups(
    keyword_groups: list[dict[str, list[str] | str]],
    max_groups: int = 5,
) -> Iterable[list[dict[str, list[str] | str]]]:
    """NAVER DataLab Search API의 1회 요청 group 제한에 맞춰 분할한다."""
    for start in range(0, len(keyword_groups), max_groups):
        yield keyword_groups[start:start + max_groups]


def chunk_keyword_groups_with_anchor(
    keyword_groups: list[dict[str, list[str] | str]],
    anchor_group: dict[str, list[str] | str] = ANCHOR_KEYWORD_GROUP,
    max_groups: int = 5,
) -> Iterable[list[dict[str, list[str] | str]]]:
    """각 NAVER 요청에 공통 anchor를 포함하되 전체 group 수는 5개 이하로 유지한다."""
    if max_groups < 2:
        raise ValueError("max_groups must be at least 2 when using an anchor")
    sectors = [g for g in keyword_groups if g.get("groupName") != anchor_group.get("groupName")]
    step = max_groups - 1
    for start in range(0, len(sectors), step):
        yield [anchor_group] + sectors[start:start + step]


def _fetch_naver_datalab_chunk(
    client_id: str,
    client_secret: str,
    keyword_groups: list[dict[str, list[str] | str]],
    start_date: str,
    end_date: str,
    time_unit: str = "month",
    timeout: int = 20,
    max_attempts: int = 3,
) -> pd.DataFrame:
    payload = build_payload(keyword_groups, start_date, end_date, time_unit)
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json",
    }
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 200:
                return parse_response_to_frame(response.json())
            logger.warning("NAVER DataLab status=%s attempt=%s", response.status_code, attempt)
            if response.status_code in {400, 401, 403}:
                logger.warning("NAVER DataLab 인증/요청 오류. 키 값은 로그에 출력하지 않습니다.")
                break
        except Exception as exc:
            logger.warning("NAVER DataLab request failed attempt=%s: %s", attempt, exc)
        time.sleep(2 ** (attempt - 1))
    return pd.DataFrame(columns=["period", "group_name", "keywords", "ratio"])


def fetch_naver_datalab(
    client_id: str,
    client_secret: str,
    keyword_groups: list[dict[str, list[str] | str]],
    start_date: str,
    end_date: str,
    time_unit: str = "month",
    timeout: int = 20,
    max_attempts: int = 3,
    anchor_group: dict[str, list[str] | str] | None = None,
) -> pd.DataFrame:
    frames = []
    chunker = (
        chunk_keyword_groups_with_anchor(keyword_groups, anchor_group, max_groups=5)
        if anchor_group is not None
        else chunk_keyword_groups(keyword_groups, max_groups=5)
    )
    for chunk_id, chunk in enumerate(chunker):
        frame = _fetch_naver_datalab_chunk(
            client_id,
            client_secret,
            chunk,
            start_date,
            end_date,
            time_unit,
            timeout=timeout,
            max_attempts=max_attempts,
        )
        if not frame.empty:
            frame["chunk_id"] = chunk_id
            frames.append(frame)
        time.sleep(0.2)
    if not frames:
        return pd.DataFrame(columns=["period", "group_name", "keywords", "ratio", "chunk_id"])
    return pd.concat(frames, ignore_index=True).sort_values(["chunk_id", "group_name", "period"]).reset_index(drop=True)


def calculate_anchor_normalized_factors(
    df: pd.DataFrame,
    anchor_group_name: str = ANCHOR_GROUP_NAME,
) -> pd.DataFrame:
    """같은 chunk의 anchor 대비 상대검색강도와 단순 모멘텀 팩터를 계산한다."""
    if df.empty:
        return pd.DataFrame()
    required = {"period", "group_name", "keywords", "ratio", "chunk_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing columns for factor calculation: {sorted(missing)}")

    base = df.copy()
    base["ratio"] = pd.to_numeric(base["ratio"], errors="coerce")
    anchors = base[base["group_name"] == anchor_group_name][["chunk_id", "period", "ratio"]].rename(columns={"ratio": "anchor_ratio"})
    sectors = base[base["group_name"] != anchor_group_name].copy()
    factors = sectors.merge(anchors, on=["chunk_id", "period"], how="left")
    factors["anchor_relative_ratio"] = factors.apply(
        lambda row: None if not row["anchor_ratio"] or pd.isna(row["anchor_ratio"]) else row["ratio"] / row["anchor_ratio"] * 100,
        axis=1,
    )
    factors = factors.sort_values(["group_name", "period"]).reset_index(drop=True)
    factors["momentum_1p"] = factors.groupby("group_name")["anchor_relative_ratio"].diff(1)
    factors["momentum_3p"] = factors.groupby("group_name")["anchor_relative_ratio"].diff(3)
    rolling_mean = factors.groupby("group_name")["anchor_relative_ratio"].transform(lambda s: s.rolling(12, min_periods=3).mean())
    rolling_std = factors.groupby("group_name")["anchor_relative_ratio"].transform(lambda s: s.rolling(12, min_periods=3).std())
    factors["zscore_12p"] = (factors["anchor_relative_ratio"] - rolling_mean) / rolling_std
    return factors[[
        "period", "group_name", "keywords", "chunk_id", "ratio", "anchor_ratio",
        "anchor_relative_ratio", "momentum_1p", "momentum_3p", "zscore_12p",
    ]]


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_\-]+", "_", value).strip("_").lower()
    return slug or "series"


def save_frame(df: pd.DataFrame, save_dir: str | Path, dataset_name: str, time_unit: str) -> Path:
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / f"naver_datalab_{safe_slug(dataset_name)}_{safe_slug(time_unit)}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def collect(
    keyword_groups: list[dict[str, list[str] | str]] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    time_unit: str = "month",
    dataset_name: str | None = None,
    save_dir: str | Path = SAVE_DIR,
    universe: str = "theme",
    anchor_normalize: bool | None = None,
) -> tuple[pd.DataFrame, Path | None]:
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.error("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET 미설정 — 수집 종료")
        return pd.DataFrame(columns=["period", "group_name", "keywords", "ratio"]), None

    today = date.today()
    start_date = start_date or default_start_date(today)
    end_date = end_date or today.isoformat()
    keyword_groups = keyword_groups or get_keyword_groups(universe)
    dataset_name = dataset_name or ("sector_interest" if universe == "sector" else "theme_interest")
    if anchor_normalize is None:
        anchor_normalize = universe == "sector"

    df = fetch_naver_datalab(
        client_id,
        client_secret,
        keyword_groups,
        start_date,
        end_date,
        time_unit,
        anchor_group=ANCHOR_KEYWORD_GROUP if anchor_normalize else None,
    )
    if df.empty:
        logger.warning("NAVER DataLab 수집 결과 없음")
        return df, None

    path = save_frame(df, save_dir, dataset_name, time_unit)
    logger.info("NAVER DataLab raw 저장 완료: %s (%d rows, %s~%s)", path, len(df), df["period"].min(), df["period"].max())

    if anchor_normalize:
        factors = calculate_anchor_normalized_factors(df)
        factor_path = save_frame(factors, save_dir, f"{dataset_name}_factor", time_unit)
        logger.info("NAVER DataLab factor 저장 완료: %s (%d rows, %d groups)", factor_path, len(factors), factors["group_name"].nunique())
    return df, path


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect NAVER DataLab theme/sector interest data.")
    parser.add_argument("--start-date", default=None, help="YYYY-MM-DD. Default: about 5 years ago")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD. Default: today")
    parser.add_argument("--time-unit", choices=["date", "week", "month"], default="month")
    parser.add_argument("--dataset-name", default=None)
    parser.add_argument("--universe", choices=["theme", "sector"], default="theme")
    parser.add_argument("--no-anchor-normalize", action="store_true", help="sector 수집에서도 anchor factor 생성을 끕니다")
    return parser.parse_args(argv)


def run(argv: Iterable[str] | None = None):
    args = parse_args(argv)
    return collect(
        start_date=args.start_date,
        end_date=args.end_date,
        time_unit=args.time_unit,
        dataset_name=args.dataset_name,
        universe=args.universe,
        anchor_normalize=False if args.no_anchor_normalize else None,
    )


if __name__ == "__main__":
    run()
