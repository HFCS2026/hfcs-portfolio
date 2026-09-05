#!/usr/bin/env python3
"""
HFCS Live Portfolio Sync
========================

Pulls photos from the two Jotform inspection forms, pairs before/after shots,
strips location data out of them, resizes them for the web, and writes the
gallery feed that happyfamilycleaningsolutions.com/portfolio reads.

    Pre-Job Walkthrough  ->  "Before Pictures"
    Job Closeout         ->  "After Pictures"

NOTHING publishes unless an owner approves the job. There are two ways to approve,
and either one works:

  1. Star (flag) the Job Closeout submission in the Jotform inbox, OR
  2. Put #portfolio anywhere in that submission's Notes / Comments field.

The keyword is the reliable one -- it is plain text the API always returns. The star
depends on Jotform exposing its flag through the API, which is not guaranteed.
Writing NO PHOTOS in the Notes blocks a job outright, even if it is starred.

Photos are taken on every job as part of the inspection process, so the control is at
the CAMERA, not at a consent question -- see "Job Photo Standards & Word Tracks".

Run it:
    python sync_portfolio.py --dry-run     # show what would publish, write nothing
    python sync_portfolio.py               # build docs/gallery.json + docs/images/
    python sync_portfolio.py --sample      # build a demo gallery with fake data

Environment variables (set as GitHub Secrets in the Actions run):
    JOTFORM_API_KEY   required
    PRE_FORM_ID       default 261183496401052
    POST_FORM_ID      default 261183572696063
    JOTFORM_API_BASE  default https://api.jotform.com
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageOps

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
IMAGES = DOCS / "images"
SEED = ROOT / "seed"
FEED = DOCS / "gallery.json"
STATUS = DOCS / "status.json"

API_KEY = os.environ.get("JOTFORM_API_KEY", "").strip()
API_BASE = os.environ.get("JOTFORM_API_BASE", "https://api.jotform.com").rstrip("/")
PRE_FORM_ID = os.environ.get("PRE_FORM_ID", "261183496401052").strip()
POST_FORM_ID = os.environ.get("POST_FORM_ID", "261183572696063").strip()

# How the owner approves a job for the website.
#   "flag"  -> star the closeout in Jotform, OR put #portfolio in its Notes  (default)
#   "field" -> answer Yes to a "Publish to website" question on the closeout form
#   "none"  -> publish every matched job (not recommended)
PUBLISH_GATE = os.environ.get("PUBLISH_GATE", "flag").strip().lower()

# The word an owner types into the closeout Notes to approve a job for the website,
# and the word that blocks one no matter what else says.
APPROVE_KEYWORD = os.environ.get("APPROVE_KEYWORD", "#portfolio").strip().lower()
BLOCK_KEYWORD = os.environ.get("BLOCK_KEYWORD", "no photos").strip().lower()

# Off by default: photos are part of the standard inspection process, not a per-job ask.
# Set REQUIRE_CONSENT=true only if a photo-release question is ever added back to the
# walkthrough form and you want the sync to honour it.
REQUIRE_CONSENT = os.environ.get("REQUIRE_CONSENT", "false").strip().lower() == "true"

# How far apart a walkthrough and its closeout can be and still be the same job.
MAX_PAIR_DAYS = int(os.environ.get("MAX_PAIR_DAYS", "45"))

# Image output
FULL_MAX = 1600      # long edge of the full-size web image
THUMB_MAX = 700      # long edge of the grid thumbnail
JPEG_QUALITY = 82

# Question-text matching. Jotform question IDs change when a form is edited,
# so we match on the visible label instead. Lowercase, substring match.
FIELD_HINTS = {
    "before":   ["before picture", "before photo", "before image"],
    "after":    ["after picture", "after photo", "after image"],
    "customer": ["customer name", "client name", "customer"],
    "date":     ["date"],
    "service":  ["service type", "service"],
    "crew":     ["crew lead"],
    "notes":    ["notes"],
    "consent":  ["photo release", "photo permission", "photo consent",
                 "ok us using", "okay us using", "website and marketing",
                 "before-and-after photos of this job", "photos for marketing",
                 "permission to photograph", "ok photos"],
    "publish":  ["publish to website", "feature on website", "add to portfolio"],
    "caption":  ["portfolio caption", "website caption"],
}

SERVICE_ALIASES = {
    "house cleaning": "House Cleaning",
    "residential cleaning": "House Cleaning",
    "deep clean": "House Cleaning",
    "deep cleaning": "House Cleaning",
    "standard clean": "House Cleaning",
    "move out": "Move-Out Cleaning",
    "move-out": "Move-Out Cleaning",
    "move in": "Move-Out Cleaning",
    "check-in": "Check-In Light Cleaning",
    "check in": "Check-In Light Cleaning",
    "junk": "Junk Removal",
    "junk removal": "Junk Removal",
    "cleanout": "Junk Removal",
    "clean out": "Junk Removal",
    "pet waste": "Pet Waste Removal",
    "pet": "Pet Waste Removal",
    "tile": "Tile & Grout",
    "grout": "Tile & Grout",
    "commercial": "Commercial",
    "post-construction": "Post-Construction",
    "post construction": "Post-Construction",
}


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------
# Jotform
# --------------------------------------------------------------------------

def fetch_submissions(form_id: str) -> list[dict]:
    """Every submission on a form, newest first, paged."""
    out: list[dict] = []
    offset = 0
    while True:
        r = requests.get(
            f"{API_BASE}/form/{form_id}/submissions",
            params={"apiKey": API_KEY, "limit": 100, "offset": offset,
                    "orderby": "created_at"},
            timeout=60,
        )
        if r.status_code == 401:
            sys.exit("Jotform rejected the API key. Check the JOTFORM_API_KEY secret.")
        r.raise_for_status()
        batch = r.json().get("content") or []
        out.extend(batch)
        if len(batch) < 100:
            break
        offset += 100
    return out


def find_answer(answers: dict, kind: str):
    """Pull one answer out of a submission by matching the question label."""
    hints = FIELD_HINTS[kind]
    best = None
    for a in answers.values():
        label = (a.get("text") or "").strip().lower()
        if not label:
            continue
        for rank, hint in enumerate(hints):
            if hint in label:
                if best is None or rank < best[0]:
                    best = (rank, a)
                break
    return best[1] if best else None


def answer_text(a) -> str:
    if not a:
        return ""
    v = a.get("answer")
    if v is None:
        return ""
    if isinstance(v, dict):
        # Jotform date fields arrive as {"month": "08", "day": "14", "year": "2026"}
        if {"month", "day", "year"} <= set(v):
            try:
                return f"{int(v['year']):04d}-{int(v['month']):02d}-{int(v['day']):02d}"
            except (ValueError, TypeError):
                return ""
        return " ".join(str(x) for x in v.values() if x)
    if isinstance(v, list):
        return ", ".join(str(x) for x in v if x)
    return str(v).strip()


def answer_files(a) -> list[str]:
    if not a:
        return []
    v = a.get("answer")
    if isinstance(v, list):
        return [str(u).strip() for u in v if str(u).strip().startswith("http")]
    if isinstance(v, str) and v.strip().startswith("http"):
        return [u.strip() for u in v.split("\n") if u.strip().startswith("http")]
    return []


def norm_name(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def norm_service(s: str) -> str:
    low = (s or "").strip().lower()
    if not low:
        return "Other"
    for key, val in SERVICE_ALIASES.items():
        if key in low:
            return val
    return (s or "Other").strip().title()


def parse_date(text: str, fallback: str) -> str:
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Jotform's created_at looks like "2026-08-14 09:12:33"
    return (fallback or "")[:10]


def read_submission(sub: dict, side: str) -> dict:
    answers = sub.get("answers") or {}
    photos = answer_files(find_answer(answers, "before" if side == "pre" else "after"))
    return {
        "id": sub.get("id"),
        "side": side,
        "flag_raw": str(sub.get("flag", "")),
        "flag": str(sub.get("flag", "0")).strip().lower() in ("1", "true", "yes"),
        "created": sub.get("created_at", ""),
        "customer": answer_text(find_answer(answers, "customer")),
        "date": parse_date(answer_text(find_answer(answers, "date")), sub.get("created_at", "")),
        "service": answer_text(find_answer(answers, "service")),
        "crew": answer_text(find_answer(answers, "crew")),
        "notes": answer_text(find_answer(answers, "notes")),
        "caption": answer_text(find_answer(answers, "caption")),
        "consent": answer_text(find_answer(answers, "consent")),
        "publish": answer_text(find_answer(answers, "publish")),
        "photos": photos,
    }


def says_yes(text: str) -> bool:
    return (text or "").strip().lower().startswith(("yes", "y ", "true", "approved", "ok"))


# --------------------------------------------------------------------------
# Pairing
# --------------------------------------------------------------------------

def pair_jobs(pres: list[dict], posts: list[dict]) -> tuple[list[dict], list[dict]]:
    """Match each closeout to the nearest earlier walkthrough for the same customer."""
    used: set[str] = set()
    jobs, orphans = [], []

    for post in sorted(posts, key=lambda p: p["date"]):
        key = norm_name(post["customer"])
        best, best_gap = None, None
        for pre in pres:
            if pre["id"] in used or norm_name(pre["customer"]) != key or not key:
                continue
            try:
                d1 = datetime.strptime(pre["date"], "%Y-%m-%d")
                d2 = datetime.strptime(post["date"], "%Y-%m-%d")
            except ValueError:
                continue
            gap = (d2 - d1).days
            if gap < -1 or gap > MAX_PAIR_DAYS:
                continue
            if best_gap is None or gap < best_gap:
                best, best_gap = pre, gap
        if best:
            used.add(best["id"])
            jobs.append({"pre": best, "post": post})
        else:
            orphans.append(post)
    return jobs, orphans


def gate_passes(job: dict) -> tuple[bool, str]:
    """Decide whether one matched job may go on the website, and say why."""
    pre, post = job["pre"], job["post"]
    notes = " ".join([post["notes"], pre["notes"]]).lower()

    # A customer asked us not to use their photos. This beats everything else.
    if BLOCK_KEYWORD and BLOCK_KEYWORD in notes:
        return False, f"notes say '{BLOCK_KEYWORD}' — customer opted out"

    if PUBLISH_GATE == "field":
        if not says_yes(post["publish"]):
            return False, "closeout 'publish to website' is not Yes"
    elif PUBLISH_GATE != "none":
        starred = post["flag"]
        keyworded = bool(APPROVE_KEYWORD) and APPROVE_KEYWORD in notes
        if not (starred or keyworded):
            return False, (f"not approved — star the closeout in Jotform, "
                           f"or put {APPROVE_KEYWORD} in its Notes")

    if REQUIRE_CONSENT:
        if not says_yes(pre["consent"]):
            return False, "no photo release on the walkthrough"

    if not pre["photos"] or not post["photos"]:
        return False, "needs both before and after photos"
    return True, ""


def approval_source(job: dict) -> str:
    post = job["post"]
    notes = " ".join([post["notes"], job["pre"]["notes"]]).lower()
    if post["flag"]:
        return "starred in Jotform"
    if APPROVE_KEYWORD and APPROVE_KEYWORD in notes:
        return f"{APPROVE_KEYWORD} in notes"
    return "gate disabled"


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------

def slug(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def download(url: str) -> bytes | None:
    for attempt_url in (url, f"{url}{'&' if '?' in url else '?'}apiKey={API_KEY}"):
        try:
            r = requests.get(attempt_url, timeout=90)
            if r.status_code == 200 and r.content[:2] not in (b"<h", b"<!"):
                return r.content
        except requests.RequestException:
            continue
    return None


def process_image(url: str) -> dict | None:
    """Download once, strip EXIF (including GPS), resize, cache on disk."""
    key = slug(url)
    full_path = IMAGES / f"{key}.jpg"
    thumb_path = IMAGES / f"{key}_t.jpg"
    meta_path = IMAGES / f"{key}.json"

    if full_path.exists() and thumb_path.exists() and meta_path.exists():
        return json.loads(meta_path.read_text())

    raw = download(url)
    if not raw:
        log(f"    ! could not download {url[:90]}")
        return None

    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)          # honour phone rotation
        img = img.convert("RGB")                    # and drop every EXIF tag with it
    except Exception as exc:                        # noqa: BLE001
        log(f"    ! not an image ({exc}): {url[:90]}")
        return None

    full = img.copy()
    full.thumbnail((FULL_MAX, FULL_MAX), Image.LANCZOS)
    full.save(full_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)

    thumb = img.copy()
    thumb.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    thumb.save(thumb_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)

    meta = {"src": f"images/{key}.jpg", "thumb": f"images/{key}_t.jpg",
            "w": full.width, "h": full.height}
    meta_path.write_text(json.dumps(meta))
    return meta


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def build_item(job: dict) -> dict | None:
    """One job = every before shot and every after shot, kept as two groups.

    We deliberately do NOT pair individual photos. Crews do not shoot the same
    rooms in the same order, and guessing produces a bathroom labelled "before"
    next to a living room labelled "after" — which reads as carelessness to the
    exact customer we are trying to win.
    """
    pre, post = job["pre"], job["post"]
    before = [m for m in (process_image(u) for u in pre["photos"]) if m]
    after = [m for m in (process_image(u) for u in post["photos"]) if m]
    if not before and not after:
        return None

    service = norm_service(pre["service"])
    caption = post["caption"] or pre["caption"] or ""
    return {
        "id": f"jf-{post['id']}",
        "service": service,
        "date": post["date"] or pre["date"],
        "title": caption or service,
        "caption": caption,
        "before": before,
        "after": after,
        "source": "jotform",
    }


def load_seed() -> list[dict]:
    """Hand-picked photos that predate the automation. seed/seed.json describes them."""
    manifest = SEED / "seed.json"
    if not manifest.exists():
        return []
    items = json.loads(manifest.read_text()).get("items", [])
    out = []
    for it in items:
        before = [m for m in (seed_image(n) for n in it.get("before", [])) if m]
        after = [m for m in (seed_image(n) for n in it.get("after", [])) if m]
        if not before and not after:
            continue
        out.append({
            "id": it.get("id") or f"seed-{slug(json.dumps(it, sort_keys=True))}",
            "service": norm_service(it.get("service", "")),
            "date": it.get("date", ""),
            "title": it.get("title") or norm_service(it.get("service", "")),
            "caption": it.get("caption", ""),
            "before": before,
            "after": after,
            "source": "seed",
        })
    return out


def seed_image(name: str | None) -> dict | None:
    if not name:
        return None
    src = SEED / "images" / name
    if not src.exists():
        log(f"    ! seed image missing: {name}")
        return None
    key = "seed-" + hashlib.sha1(name.encode()).hexdigest()[:10]
    full_path, thumb_path = IMAGES / f"{key}.jpg", IMAGES / f"{key}_t.jpg"
    if not (full_path.exists() and thumb_path.exists()):
        img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        full = img.copy(); full.thumbnail((FULL_MAX, FULL_MAX), Image.LANCZOS)
        full.save(full_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        thumb = img.copy(); thumb.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
        thumb.save(thumb_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    with Image.open(full_path) as im:
        w, h = im.size
    return {"src": f"images/{key}.jpg", "thumb": f"images/{key}_t.jpg", "w": w, "h": h}


def write_feed(items: list[dict]) -> None:
    items.sort(key=lambda i: (i.get("date") or "", i["id"]), reverse=True)
    services = sorted({i["service"] for i in items})
    feed = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(items),
        "services": services,
        "items": items,
    }
    DOCS.mkdir(parents=True, exist_ok=True)
    FEED.write_text(json.dumps(feed, indent=1))
    log(f"\nWrote {FEED.relative_to(ROOT)} — {len(items)} jobs, {len(services)} services.")

    used = {Path(m["src"]).name for i in items for m in iter_media(i)}
    used |= {Path(m["thumb"]).name for i in items for m in iter_media(i)}
    used |= {n.replace(".jpg", ".json") for n in used}
    removed = 0
    for f in IMAGES.glob("*"):
        if f.name not in used:
            f.unlink(); removed += 1
    if removed:
        log(f"Cleaned up {removed} unused image files.")


def write_status(pres, posts, jobs, orphans, decided) -> None:
    """A small, name-free diagnostic file published beside the gallery.

    It exists so the run can be checked without opening the Actions log. It
    deliberately carries NO customer names and NO photo URLs — only dates,
    service types, counts and the reason each job was or was not published.
    """
    rows = []
    for job, ok, why in decided:
        post, pre = job["post"], job["pre"]
        rows.append({
            "ref": str(post["id"])[-6:],
            "date": post["date"] or pre["date"],
            "service": norm_service(pre["service"]),
            "before_photos": len(pre["photos"]),
            "after_photos": len(post["photos"]),
            "starred": post["flag"],
            "flag_raw": post.get("flag_raw", ""),
            "published": ok,
            "reason": why or approval_source(job),
        })
    STATUS.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gate": PUBLISH_GATE,
        "approve_keyword": APPROVE_KEYWORD,
        "require_consent": REQUIRE_CONSENT,
        "counts": {
            "walkthroughs": len(pres),
            "closeouts": len(posts),
            "matched": len(jobs),
            "unmatched_closeouts": len(orphans),
            "published": sum(1 for _, ok, _ in decided if ok),
            "held": sum(1 for _, ok, _ in decided if not ok),
        },
        "jobs": rows,
    }, indent=1))
    log(f"Wrote {STATUS.relative_to(ROOT)} (no names in it — safe to be public).")


def iter_media(item: dict):
    yield from item.get("before", [])
    yield from item.get("after", [])


# --------------------------------------------------------------------------
# Sample mode — a preview with generated placeholder photos, no API key needed
# --------------------------------------------------------------------------

def make_sample() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    demos = [
        ("Junk Removal", "Garage cleanout, Largo", "2026-08-28",
         [((120, 110, 100), "BEFORE"), ((225, 232, 238), "AFTER")]),
        ("House Cleaning", "2 bed 2 bath deep clean, Clearwater", "2026-08-22",
         [((140, 130, 118), "BEFORE"), ((238, 244, 248), "AFTER")]),
        ("Pet Waste Removal", "HOA common area, Pinellas Park", "2026-08-19",
         [((122, 128, 108), "BEFORE"), ((196, 216, 178), "AFTER")]),
        ("House Cleaning", "Move-out kitchen reset, Seminole", "2026-08-11",
         [((132, 122, 112), "BEFORE"), ((240, 245, 249), "AFTER")]),
    ]
    items = []
    for n, (service, title, date, shades) in enumerate(demos):
        groups = {}
        for (rgb, label) in shades:
            key = f"sample-{n}-{label.lower()}"
            img = Image.new("RGB", (1400, 1050), rgb)
            d = ImageDraw.Draw(img)
            for i in range(0, 1400, 60):
                d.line([(i, 0), (i - 300, 1050)], fill=tuple(max(0, c - 12) for c in rgb), width=18)
            d.rectangle([40, 40, 360, 130], fill=(41, 171, 226))
            img.save(IMAGES / f"{key}.jpg", "JPEG", quality=82)
            img.resize((700, 525)).save(IMAGES / f"{key}_t.jpg", "JPEG", quality=82)
            groups[label.lower()] = [{"src": f"images/{key}.jpg", "thumb": f"images/{key}_t.jpg",
                                      "w": 1400, "h": 1050}]
        items.append({"id": f"sample-{n}", "service": service, "date": date,
                      "title": title, "caption": "",
                      "before": groups["before"], "after": groups["after"],
                      "source": "sample"})
    write_feed(items)
    log("Sample gallery built. Open docs/index.html to preview it.")


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Sync HFCS job photos into the live portfolio.")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would publish; download nothing, write nothing")
    ap.add_argument("--sample", action="store_true",
                    help="build a demo gallery with placeholder images and no API key")
    args = ap.parse_args()

    if args.sample:
        make_sample()
        return

    if not API_KEY:
        sys.exit("JOTFORM_API_KEY is not set. See README-SETUP.md step 3.")

    IMAGES.mkdir(parents=True, exist_ok=True)

    log(f"Pulling Pre-Job Walkthrough  ({PRE_FORM_ID}) ...")
    pres = [read_submission(s, "pre") for s in fetch_submissions(PRE_FORM_ID)]
    log(f"  {len(pres)} walkthroughs")
    log(f"Pulling Job Closeout         ({POST_FORM_ID}) ...")
    posts = [read_submission(s, "post") for s in fetch_submissions(POST_FORM_ID)]
    log(f"  {len(posts)} closeouts")

    jobs, orphans = pair_jobs(pres, posts)
    log(f"\nMatched {len(jobs)} before/after jobs. {len(orphans)} closeouts had no walkthrough.")
    for o in orphans:
        log(f"  unmatched closeout: {o['customer'] or '(no name)'} {o['date']}")

    decided = [(job, *gate_passes(job)) for job in jobs]
    approved = [(j, w) for j, ok, w in decided if ok]
    held = [(j, w) for j, ok, w in decided if not ok]

    log(f"\nApproved for the website: {len(approved)}")
    for job, _ in approved:
        log(f"  + {job['post']['customer']} — {norm_service(job['pre']['service'])} — "
            f"{job['post']['date']} — approved by: {approval_source(job)}")
    log(f"Held back: {len(held)}")
    for job, why in held:
        log(f"  - {job['post']['customer'] or '(no name)'} {job['post']['date']}: {why}")
        log(f"      (raw flag value Jotform returned: {job['post'].get('flag_raw', '')!r})")

    if args.dry_run:
        log("\nDry run — nothing downloaded, nothing written.")
        return

    items = [i for i in (build_item(j) for j, _ in approved) if i]
    items += load_seed()
    write_feed(items)
    write_status(pres, posts, jobs, orphans, decided)


if __name__ == "__main__":
    main()
