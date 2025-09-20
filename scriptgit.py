import requests
import time
import json
import os
from requests.auth import HTTPBasicAuth
from datetime import datetime
import re
import unicodedata

# ---------- CONFIG ----------
NEWS_API_KEYS = [
    "",
    "",
]

NewS_KEYWORDS = [
   
    "general"
   
]
NewS_LANG = "en"
NewS_COUNTRY = "us"
PAGE_SIZE = 10
START_PAGE = 1
MAX_PAGES = 100
REQUEST_DELAY = 1.0

APILINK = ""
WP_SITE = "https://pakalertpress.com"
WP_USER = "wpadministrator"
WP_APP_PASSWORD = ""
WP_POST_STATUS = "publish"
PROCESSED_FILE = "imported_ids.json"

STOPWORDS = {
    "the", "and", "that", "with", "from", "this", "there", "have",
    "were", "which", "about", "they", "their", "would", "could",
    "should", "your", "ours", "into", "what", "when", "where",
    "them", "then", "will", "been", "like", "just", "some",
    "more", "than", "only", "other", "such", "because", "also",
    "does", "while", "after", "before", "over", "under"
}
# ----------------------------

current_key_index = 0


def load_processed_ids(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_processed_ids(path, ids_set):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(ids_set), f, indent=2)


def fetch_with_failover(query, page_size, page, lang="en", country="us"):
    """Fetch data from News with automatic key failover."""
    global current_key_index

    while current_key_index < len(NEWS_API_KEYS):
        api_key = NEWS_API_KEYS[current_key_index]
        url = (
            f"{APILINK}?q={requests.utils.quote(query)}&lang={lang}&country={country}"
            f"&max={page_size}&page={page}&apikey={api_key}"
        )
        print(f"Fetching with API key {current_key_index+1}: {url}")

        try:
            resp = requests.get(url, timeout=30)
            data = resp.json()

            
            if "errors" in data and any("request limit" in e.lower() for e in data["errors"]):
                print(f"API key {current_key_index+1} quota finished. Switching to next key...")
                current_key_index += 1
                continue 

            resp.raise_for_status()
            return data

        except Exception as e:
            print(f" API key {current_key_index+1} failed:", e)
            current_key_index += 1

    raise RuntimeError("All API keys exhausted. Please add more keys.")


def get_or_create_term(wp_site, wp_user, wp_app_pass, taxonomy, name):
    search_url = f"{wp_site.rstrip('/')}/wp-json/wp/v2/{taxonomy}?search={name}"
    resp = requests.get(search_url, auth=HTTPBasicAuth(wp_user, wp_app_pass), timeout=30)
    if resp.status_code == 200:
        results = resp.json()
        for r in results:
            if r.get("name", "").lower() == name.lower():
                return r["id"]
    create_resp = requests.post(
        f"{wp_site.rstrip('/')}/wp-json/wp/v2/{taxonomy}",
        auth=HTTPBasicAuth(wp_user, wp_app_pass),
        headers={"Content-Type": "application/json"},
        json={"name": name}
    )
    if create_resp.status_code in (200, 201):
        return create_resp.json()["id"]
    else:
        print(f"Failed to create {taxonomy}: {name}", create_resp.text)
        return None


def extract_keywords(text, limit=8):
    if not text:
        return []
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    unique = []
    for w in filtered:
        if w not in unique:
            unique.append(w)
    return unique[:limit]


def determine_category(title, content):
    text = f"{title} {content}".lower()

    categories = {
        "Politics": [r"\bpolitic(s)?\b", r"\belection(s)?\b", r"\bparliament\b", r"\bgovernment\b", r"\bpolicy\b"],
        "Crime": [r"\bcrime(s)?\b", r"\bmurder(s)?\b", r"\bpolice\b", r"\btheft\b", r"\bfraud\b", r"\bscam(s)?\b", r"\bcorruption\b"],
        "Sports": [r"\bsport(s)?\b", r"\bmatch(es)?\b", r"\btournament(s)?\b", r"\bworld cup\b", r"\bleague(s)?\b", r"\bplayer(s)?\b"],
        "Technology": [r"\btech(nology)?\b", r"\bai\b", r"\bsoftware\b", r"\bdigital\b", r"\bblockchain\b", r"\bcloud\b", r"\bmachine learning\b"],
        "Business": [r"\bbusiness(es)?\b", r"\bmarket(s)?\b", r"\beconom(y|ies)\b", r"\bstock(s)?\b", r"\btrade\b", r"\bfinance\b", r"\bcorporate\b"],
        "Cybersecurity": [r"\bcyber\b", r"\bhack(ing|er)?\b", r"\bransomware\b", r"\bdata breach\b", r"\bphishing\b", r"\bmalware\b", r"\bencryption\b"]
    }

    for category, patterns in categories.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return category

    return "General"


def upload_image_to_wp(wp_site, wp_user, wp_app_pass, image_url, title="Thumbnail"):
    try:
        img_data = requests.get(image_url, timeout=30).content
    except Exception as e:
        print("Failed to download image:", e)
        return None

    media_url = f"{wp_site.rstrip('/')}/wp-json/wp/v2/media"

    def sanitize_filename(name):
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")
        name = re.sub(r'[^A-Za-z0-9._-]', "_", name)
        return name or "image.jpg"

    filename = sanitize_filename(image_url.split("/")[-1].split("?")[0])
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    resp = requests.post(
        media_url,
        auth=HTTPBasicAuth(wp_user, wp_app_pass),
        headers=headers,
        data=img_data,
        timeout=60
    )
    if resp.status_code in (200, 201):
        return resp.json().get("id")
    else:
        print("Failed to upload image:", resp.status_code, resp.text)
        return None


def create_wp_post(wp_site, wp_user, wp_app_pass, title, html_content,
                   date_iso=None, status="publish", tags=None,
                   categories=None, featured_media=None):
    url = f"{wp_site.rstrip('/')}/wp-json/wp/v2/posts"
    payload = {"title": title, "content": html_content, "status": status}
    if tags:
        payload["tags"] = tags
    if categories:
        payload["categories"] = categories
    if featured_media:
        payload["featured_media"] = featured_media
    if date_iso:
        try:
            dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
            payload["date"] = dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            pass
    return requests.post(
        url,
        auth=HTTPBasicAuth(wp_user, wp_app_pass),
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60
    )


def main():
    print("Starting News -> WordPress importer with failover API keys")
    processed = load_processed_ids(PROCESSED_FILE)
    new_processed = set()
    total_posted = 0

    for keyword in NewS_KEYWORDS:
        print(f"\n===== Fetching articles for keyword: {keyword} =====")
        for page in range(START_PAGE, MAX_PAGES + 1):
            print(f"\nFetching page {page} for '{keyword}' ...")
            try:
                data = fetch_with_failover(keyword, PAGE_SIZE, page, NewS_LANG, NewS_COUNTRY)
            except RuntimeError as e:
                print(e)
                break

            articles = data.get("articles", [])
            if not articles:
                print("No more articles for this keyword; moving to next keyword.")
                break

            for a in articles:
                aid = a.get("id") or a.get("url")
                if not aid:
                    continue
                if aid in processed or aid in new_processed:
                    print("Skipping already imported:", a.get("title"))
                    continue

                parts = []
                if a.get("description"):
                    parts.append(f'<p>{a["description"]}</p>')
                if a.get("content"):
                    parts.append(f'<p>{a["content"]}</p>')

                source_name = a.get("source", {}).get("name", "")
                source_url = a.get("url", "")
                publishedAt = a.get("publishedAt", "")
                credit_html = f'<p><em>Source: {source_name} | Published: {publishedAt}</em></p>' if source_name or publishedAt else ""
                credit_line = f'<p><small>Credit: <a href="{source_url}" target="_blank" rel="nofollow">{source_name or source_url}</a></small></p>'
                html_content = "\n".join(parts + [credit_html, credit_line])
                title = a.get("title", "News Article")

                featured_id = None
                if a.get("image"):
                    featured_id = upload_image_to_wp(WP_SITE, WP_USER, WP_APP_PASSWORD, a["image"])

                keywords = extract_keywords(title + " " + a.get("content", ""))
                tag_ids = []
                for kw in keywords:
                    tid = get_or_create_term(WP_SITE, WP_USER, WP_APP_PASSWORD, "tags", kw.capitalize())
                    if tid:
                        tag_ids.append(tid)
                cat_name = determine_category(title, a.get("content", ""))
                cat_id = get_or_create_term(WP_SITE, WP_USER, WP_APP_PASSWORD, "categories", cat_name)

                try:
                    resp = create_wp_post(
                        WP_SITE, WP_USER, WP_APP_PASSWORD,
                        title, html_content, date_iso=publishedAt,
                        status=WP_POST_STATUS, tags=tag_ids,
                        categories=[cat_id] if cat_id else None,
                        featured_media=featured_id
                    )
                except Exception as e:
                    print("❌ Error creating WP post for:", title, e)
                    continue

                if resp.status_code in (200, 201):
                    resp_json = resp.json()
                    print("✅ Posted:", title)
                    print("URL:", resp_json.get("link"))
                    total_posted += 1
                    new_processed.add(aid)
                else:
                    print("Failed to post:", title)
                    print("Status:", resp.status_code, resp.text)
                    if resp.status_code in (401, 403):
                        print("Authentication/permission error. Stopping.")
                        save_processed_ids(PROCESSED_FILE, processed.union(new_processed))
                        return
                time.sleep(0.5)

            time.sleep(REQUEST_DELAY)

    processed.update(new_processed)
    save_processed_ids(PROCESSED_FILE, processed)
    print(f"\n🎉 Done. Total posted: {total_posted}. Processed count saved to {PROCESSED_FILE}")


if __name__ == "__main__":
    main()
