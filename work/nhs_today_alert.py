#!/usr/bin/env python3
"""Build styled NHS visa sponsorship alerts from live NHS Jobs pages."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


BASE = "https://www.jobs.nhs.uk"
TODAY = dt.date.today()
POSITIVE_PATTERNS = [
    r"applications from job seekers who require current skilled worker sponsorship.*?welcome",
    r"applications from individuals who require a skilled worker sponsorship.*?welcome",
    r"this role is eligible for visa sponsorship",
    r"role is eligible for visa sponsorship",
    r"eligible for visa sponsorship under",
    r"health and care worker visa",
]

NEGATIVE_PATTERNS = [
    r"not eligible for (?:skilled worker )?visa sponsorship",
    r"unable to (?:offer|provide|consider).*?sponsorship",
    r"does not meet .*?visa sponsorship",
    r"do not meet .*?sponsorship",
    r"must already have the right to work",
    r"applicants must already have the right to work",
    r"will not be able to sponsor",
    r"not able to sponsor",
    r"unfortunately ineligible to apply",
    r"requires? current skilled worker sponsorship.*?ineligible",
    r"requiring current skilled worker sponsorship.*?ineligible",
]


@dataclass
class Job:
    title: str
    employer: str
    location: str
    salary: str
    date_posted: str
    closing_date: str
    url: str
    evidence: str


@dataclass
class AlertConfig:
    keyword: str
    pay_band: str
    alert_title: str
    heading: str
    search_label: str
    search_link_label: str
    salary_label: str
    title_include: str


def build_search_url(keyword: str, pay_band: str, page_no: int = 1) -> str:
    query = {
        "keyword": keyword,
        "sort": "publicationDateDesc",
        "skipPhraseSuggester": "true",
    }
    if pay_band:
        query["payBand"] = pay_band
    if page_no > 1:
        query["page"] = str(page_no)
    return BASE + "/candidate/search/results?" + urllib.parse.urlencode(query)


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Codex NHS jobs alert",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(value.strip(), "%d %B %Y").date()
    except ValueError:
        return None


def extract_search_results(page: str) -> list[dict[str, str]]:
    results = []
    blocks = re.findall(
        r'<li class="nhsuk-list-panel search-result.*?</li>\s*</ul>|'
        r'<li class="nhsuk-list-panel search-result.*?</li>',
        page,
        flags=re.S,
    )

    if not blocks:
        blocks = re.findall(
            r'<li class="nhsuk-list-panel search-result.*?(?=<li class="nhsuk-list-panel search-result|</ul>)',
            page,
            flags=re.S,
        )

    for block in blocks:
        link_match = re.search(
            r'<a href="([^"]*?/candidate/jobadvert/[^"]+)"[^>]*data-test="search-result-job-title"[^>]*>(.*?)</a>',
            block,
            flags=re.S,
        )
        if not link_match:
            continue

        url = html.unescape(link_match.group(1))
        if url.startswith("/"):
            url = BASE + url
        url = url.split("?")[0]

        title = clean(link_match.group(2))
        employer_match = re.search(
            r'data-test="search-result-location".*?<h3[^>]*>(.*?)<div',
            block,
            flags=re.S,
        )
        location_match = re.search(r'<div class="location-font-size">\s*(.*?)\s*</div>', block, flags=re.S)
        salary_match = re.search(
            r'data-test="search-result-salary".*?<strong[^>]*>(.*?)</strong>',
            block,
            flags=re.S,
        )
        posted_match = re.search(
            r'data-test="search-result-publicationDate".*?<strong[^>]*>(.*?)</strong>',
            block,
            flags=re.S,
        )
        closing_match = re.search(
            r'data-test="search-result-closingDate".*?<strong[^>]*>(.*?)</strong>',
            block,
            flags=re.S,
        )

        results.append(
            {
                "title": title,
                "employer": clean(employer_match.group(1)) if employer_match else "",
                "location": clean(location_match.group(1)) if location_match else "",
                "salary": clean(salary_match.group(1)) if salary_match else "",
                "date_posted": clean(posted_match.group(1)) if posted_match else "",
                "closing_date": clean(closing_match.group(1)) if closing_match else "",
                "url": url,
            }
        )
    return results


def page_text(page: str) -> str:
    return clean(re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", page))


def find_evidence(text: str) -> str:
    for pattern in POSITIVE_PATTERNS:
        match = re.search(pattern, text, flags=re.I | re.S)
        if not match:
            continue
        return re.sub(r"\s+", " ", match.group(0)).strip()
    return ""


def has_negative_sponsorship(text: str) -> bool:
    lower = text.lower()
    return any(re.search(pattern, lower, flags=re.S) for pattern in NEGATIVE_PATTERNS)


def parse_title(page: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.S)
    return clean(match.group(1)) if match else ""


def find_jobs(max_pages: int, max_details: int, config: AlertConfig) -> list[Job]:
    candidates: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        search_page = fetch(build_search_url(config.keyword, config.pay_band, page_no))
        for result in extract_search_results(search_page):
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                candidates.append(result)
        time.sleep(0.2)

    matches: list[Job] = []
    for candidate in candidates[:max_details]:
        closing = parse_date(candidate["closing_date"])
        if closing and closing < TODAY:
            continue

        detail = fetch(candidate["url"])
        text = page_text(detail)
        if "this job is now closed" in text.lower():
            continue
        if has_negative_sponsorship(text):
            continue

        evidence = find_evidence(text)
        if not evidence:
            continue

        title = parse_title(detail) or candidate["title"]
        if config.title_include and not re.search(config.title_include, title, flags=re.I):
            continue

        matches.append(
            Job(
                title=title,
                employer=candidate["employer"],
                location=candidate["location"],
                salary=candidate["salary"],
                date_posted=candidate["date_posted"],
                closing_date=candidate["closing_date"],
                url=candidate["url"],
                evidence=evidence,
            )
        )
        time.sleep(0.2)

    return matches


def render_text_email(jobs: list[Job], config: AlertConfig) -> str:
    search_url = build_search_url(config.keyword, config.pay_band)
    lines = [
        f"{config.alert_title} - {TODAY.strftime('%d %B %Y')}",
        "",
    ]

    if not jobs:
        lines.extend(
            [
                f"No clear open {config.search_label} matches with positive visa/Skilled Worker sponsorship wording were found today.",
                "",
                "Search checked:",
                search_url,
                "",
                "Note: I excluded listings that explicitly said sponsorship is unavailable, not eligible, or requires existing right to work.",
            ]
        )
        return "\n".join(lines)

    lines.append(f"Found {len(jobs)} clear open match(es):")
    lines.append("")
    for index, job in enumerate(jobs, 1):
        lines.extend(
            [
                f"{index}. {job.title}",
                f"Employer: {job.employer}",
                f"Location: {job.location}",
                f"{config.salary_label}: {job.salary}",
                f"Date posted: {job.date_posted}",
                f"Closing date: {job.closing_date}",
                f"Sponsorship evidence: {job.evidence}",
                f"Apply: {job.url}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def days_until_closing(value: str) -> str:
    closing = parse_date(value)
    if not closing:
        return "Closing date listed"

    days = (closing - TODAY).days
    if days == 0:
        return "Closes today"
    if days == 1:
        return "Closes tomorrow"
    if days > 1:
        return f"Closes in {days} days"
    return "Closed"


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def render_job_card(job: Job, index: int) -> str:
    return f"""
      <article class="job-card">
        <div class="job-card-top">
          <span class="job-number">Match {index}</span>
          <span class="deadline">{escape(days_until_closing(job.closing_date))}</span>
        </div>
        <h2>{escape(job.title)}</h2>
        <p class="employer">{escape(job.employer)}</p>
        <div class="meta-grid">
          <div>
            <span class="label">Location</span>
            <strong>{escape(job.location)}</strong>
          </div>
          <div>
            <span class="label">Salary</span>
            <strong>{escape(job.salary)}</strong>
          </div>
          <div>
            <span class="label">Posted</span>
            <strong>{escape(job.date_posted)}</strong>
          </div>
          <div>
            <span class="label">Closing</span>
            <strong>{escape(job.closing_date)}</strong>
          </div>
        </div>
        <div class="sponsorship">
          <span class="sponsorship-label">Sponsorship evidence</span>
          <p>{escape(job.evidence)}</p>
        </div>
        <a class="apply-button" href="{escape(job.url)}">View and apply</a>
      </article>
    """


def render_html_email(jobs: list[Job], config: AlertConfig) -> str:
    date_label = TODAY.strftime("%d %B %Y")
    count_label = f"{len(jobs)} open match{'es' if len(jobs) != 1 else ''}"
    cards = "\n".join(render_job_card(job, index) for index, job in enumerate(jobs, 1))
    search_url = build_search_url(config.keyword, config.pay_band)

    if not jobs:
        cards = f"""
      <section class="empty-state">
        <h2>No clear open matches today</h2>
        <p>No {escape(config.search_label)} listings with positive visa or Skilled Worker sponsorship wording were found.</p>
        <p class="muted">Listings that said sponsorship is unavailable, not eligible, or require existing right to work were excluded.</p>
        <a class="secondary-link" href="{escape(search_url)}">Open the NHS Jobs search</a>
      </section>
        """

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(config.heading)}</title>
    <style>
      body {{
        margin: 0;
        padding: 0;
        background: #eef3f8;
        color: #17202a;
        font-family: Arial, Helvetica, sans-serif;
      }}
      a {{
        color: #005eb8;
      }}
      .page {{
        width: 100%;
        background: #eef3f8;
        padding: 24px 0;
      }}
      .container {{
        max-width: 720px;
        margin: 0 auto;
        background: #ffffff;
        border: 1px solid #d8e1ea;
      }}
      .hero {{
        background: #005eb8;
        color: #ffffff;
        padding: 28px 28px 24px;
      }}
      .eyebrow {{
        margin: 0 0 8px;
        color: #d6ecff;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0;
        text-transform: uppercase;
      }}
      h1 {{
        margin: 0;
        color: #ffffff;
        font-size: 28px;
        line-height: 1.18;
      }}
      .hero-meta {{
        margin: 18px 0 0;
        display: table;
        width: 100%;
      }}
      .hero-pill {{
        display: inline-block;
        margin: 0 8px 8px 0;
        padding: 8px 11px;
        border: 1px solid rgba(255,255,255,0.45);
        background: rgba(255,255,255,0.13);
        color: #ffffff;
        font-size: 14px;
        font-weight: 700;
      }}
      .content {{
        padding: 24px;
      }}
      .job-card {{
        margin: 0 0 18px;
        padding: 22px;
        border: 1px solid #ccd8e3;
        background: #ffffff;
      }}
      .job-card-top {{
        display: table;
        width: 100%;
        margin-bottom: 12px;
      }}
      .job-number {{
        display: inline-block;
        padding: 5px 9px;
        background: #e8f1fb;
        color: #004b93;
        font-size: 13px;
        font-weight: 700;
      }}
      .deadline {{
        float: right;
        display: inline-block;
        padding: 5px 9px;
        background: #fff4d6;
        color: #5d4300;
        font-size: 13px;
        font-weight: 700;
      }}
      h2 {{
        margin: 0 0 6px;
        color: #17202a;
        font-size: 22px;
        line-height: 1.25;
      }}
      .employer {{
        margin: 0 0 18px;
        color: #4d5c68;
        font-size: 15px;
        font-weight: 700;
      }}
      .meta-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin: 0 0 16px;
      }}
      .meta-grid div {{
        padding: 12px;
        background: #f6f9fc;
        border: 1px solid #e1e8ef;
      }}
      .label {{
        display: block;
        margin-bottom: 5px;
        color: #5d6b78;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
      }}
      .meta-grid strong {{
        display: block;
        color: #17202a;
        font-size: 14px;
        line-height: 1.35;
      }}
      .sponsorship {{
        margin: 0 0 18px;
        padding: 14px;
        border-left: 4px solid #007f61;
        background: #eef8f4;
      }}
      .sponsorship-label {{
        display: block;
        margin-bottom: 6px;
        color: #006747;
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
      }}
      .sponsorship p {{
        margin: 0;
        color: #1d352d;
        font-size: 14px;
        line-height: 1.45;
      }}
      .apply-button {{
        display: inline-block;
        padding: 12px 16px;
        background: #007f61;
        color: #ffffff !important;
        font-size: 15px;
        font-weight: 700;
        text-decoration: none;
      }}
      .empty-state {{
        padding: 24px;
        border: 1px solid #ccd8e3;
        background: #f8fbfd;
      }}
      .empty-state h2 {{
        margin-bottom: 8px;
      }}
      .empty-state p {{
        margin: 0 0 10px;
        color: #344552;
        font-size: 15px;
        line-height: 1.45;
      }}
      .muted {{
        color: #5d6b78 !important;
      }}
      .secondary-link {{
        display: inline-block;
        margin-top: 8px;
        font-weight: 700;
      }}
      .footer {{
        padding: 18px 24px 24px;
        color: #5d6b78;
        font-size: 12px;
        line-height: 1.45;
      }}
      @media screen and (max-width: 620px) {{
        .page {{
          padding: 0;
        }}
        .container {{
          width: 100%;
          border-left: 0;
          border-right: 0;
        }}
        .hero {{
          padding: 24px 18px 20px;
        }}
        h1 {{
          font-size: 24px;
        }}
        .content {{
          padding: 16px;
        }}
        .job-card {{
          padding: 18px;
        }}
        .deadline {{
          float: none;
          margin-top: 8px;
        }}
        .meta-grid {{
          display: block;
        }}
        .meta-grid div {{
          margin-bottom: 8px;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="page">
      <main class="container">
        <header class="hero">
          <p class="eyebrow">NHS Jobs alert</p>
          <h1>{escape(config.heading)}</h1>
          <div class="hero-meta">
            <span class="hero-pill">{escape(date_label)}</span>
            <span class="hero-pill">{escape(count_label)}</span>
            <span class="hero-pill">Skilled Worker wording checked</span>
          </div>
        </header>
        <section class="content">
          {cards}
        </section>
        <footer class="footer">
          Search checked: <a href="{escape(search_url)}">{escape(config.search_link_label)}</a><br>
          Listings with explicit no-sponsorship or existing-right-to-work wording were excluded.
        </footer>
      </main>
    </div>
  </body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--details", type=int, default=30)
    parser.add_argument("--keyword", default="visa sponsorship")
    parser.add_argument("--pay-band", default="BAND_3")
    parser.add_argument("--alert-title", default="NHS Band 3 visa sponsorship alert")
    parser.add_argument("--heading", default="Band 3 visa sponsorship jobs")
    parser.add_argument("--search-label", default="Band 3 NHS Jobs")
    parser.add_argument("--search-link-label", default="NHS Jobs Band 3 visa sponsorship search")
    parser.add_argument("--salary-label", default="Salary/Band")
    parser.add_argument("--title-include", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--html-output")
    args = parser.parse_args()

    config = AlertConfig(
        keyword=args.keyword,
        pay_band=args.pay_band,
        alert_title=args.alert_title,
        heading=args.heading,
        search_label=args.search_label,
        search_link_label=args.search_link_label,
        salary_label=args.salary_label,
        title_include=args.title_include,
    )

    jobs = find_jobs(args.pages, args.details, config)
    body = render_text_email(jobs, config)
    with open(args.output, "w", encoding="utf-8") as output:
        output.write(body)
    if args.html_output:
        with open(args.html_output, "w", encoding="utf-8") as output:
            output.write(render_html_email(jobs, config))
    print(f"Wrote {args.output} with {len(jobs)} match(es).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"nhs_today_alert.py failed: {exc}", file=sys.stderr)
        raise
