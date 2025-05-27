import os
import re
from typing import List, Dict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://reportcollection.inion.ru"
COMPANIES_URL = f"{BASE_URL}/organizations/"
TIMEOUT = 15

session = requests.Session()


def _soup(url: str) -> BeautifulSoup:
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def list_companies() -> List[Dict[str, str]]:
    soup = _soup(COMPANIES_URL)
    out = []
    for tr in soup.select("table tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        name = tds[1].get_text(" ", strip=True).replace("\xa0", " ")
        href = tds[4].a["href"]              # /reports/?OrganizationId=1095
        org_id = urlparse(href).query.split("=")[-1]
        out.append({"org_id": org_id, "name": name})
    return out


def list_reports(org_id: str) -> List[Dict]:
    url = f"{BASE_URL}/reports/?OrganizationId={org_id}"
    soup = _soup(url)
    reports = []
    for card in soup.select("div.card"):
        year = card.select_one("h5.card-title").get_text(strip=True)
        title = card.select_one("p.card-text").get_text(strip=True)
        dl_href = card.select_one("a.btn")["href"]
        full_url = urljoin(BASE_URL, dl_href)
        report_id = urlparse(full_url).query.split("=")[-1]
        reports.append(
            {
                "report_id": report_id,
                "year": year,
                "title": title,
                "download_url": full_url,
            }
        )
    return reports


def download_pdf(url: str, dest_dir: str) -> str:
    from tqdm import tqdm

    parsed = urlparse(url)
    fname = re.search(r"reportId=(\d+)", parsed.query).group(1) + ".pdf"
    os.makedirs(dest_dir, exist_ok=True)
    dst = os.path.join(dest_dir, fname)

    with session.get(url, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(dst, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, unit_divisor=1024
        ) as bar:
            for chunk in r.iter_content(8192):
                f.write(chunk)
                bar.update(len(chunk))
    return dst