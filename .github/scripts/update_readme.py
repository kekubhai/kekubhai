import os
import re
import requests
from datetime import datetime, timezone, timedelta


UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "kekubhai")
README_PATH = "README.md"
HISTORY_FILE = ".github/image_history.txt"
QUERY = "technology landscape coding workspace"
GITHUB_API = "https://api.github.com"


def fetch_random_image():
    """Fetch a random landscape image from Unsplash."""
    url = "https://api.unsplash.com/photos/random"
    params = {
        "query": QUERY,
        "orientation": "landscape",
        "client_id": UNSPLASH_ACCESS_KEY,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def load_history():
    """Load previously used image IDs."""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


def save_history(image_id, history):
    """Keep last 30 image IDs to avoid repeats."""
    history.append(image_id)
    history = history[-30:]
    with open(HISTORY_FILE, "w") as f:
        f.write("\n".join(history) + "\n")
    return history


def get_unique_image(history):
    """Fetch an image that wasn't used recently."""
    for _ in range(5):
        data = fetch_random_image()
        if data["id"] not in history:
            return data
    return data  # fallback after 5 attempts


def github_headers():
    """Return headers for GitHub API requests."""
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def fetch_github_stats():
    """Fetch live stats from GitHub profile."""
    stats = {
        "repos": 0,
        "stars": 0,
        "followers": 0,
        "total_commits": 0,
        "active_days": 0,
        "first_commit_year": None,
        "languages": {},
    }

    # Fetch profile info
    try:
        resp = requests.get(f"{GITHUB_API}/users/{GITHUB_USERNAME}", headers=github_headers(), timeout=15)
        resp.raise_for_status()
        profile = resp.json()
        stats["followers"] = profile.get("followers", 0)
    except Exception as e:
        print(f"Warning: Could not fetch profile: {e}")

    # Fetch all repos (paginated)
    repos = []
    page = 1
    while True:
        try:
            resp = requests.get(
                f"{GITHUB_API}/users/{GITHUB_USERNAME}/repos",
                headers=github_headers(),
                params={"per_page": 100, "page": page, "sort": "updated"},
                timeout=15,
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            repos.extend(batch)
            page += 1
        except Exception:
            break

    stats["repos"] = len(repos)
    stats["stars"] = sum(r.get("stargazers_count", 0) for r in repos)

    # Count languages
    for repo in repos:
        lang = repo.get("language")
        if lang:
            stats["languages"][lang] = stats["languages"].get(lang, 0) + 1

    # Fetch recent commit activity across top repos
    for repo in repos[:10]:
        try:
            resp = requests.get(
                f"{GITHUB_API}/repos/{GITHUB_USERNAME}/{repo['name']}/commits",
                headers=github_headers(),
                params={"per_page": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                commits = resp.json()
                stats["total_commits"] += 1
                if commits:
                    date_str = commits[0]["commit"]["author"]["date"]
                    commit_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if stats["first_commit_year"] is None or commit_date.year < stats["first_commit_year"]:
                        stats["first_commit_year"] = commit_date.year
        except Exception:
            continue

    # Estimate active days from contribution-like data
    try:
        resp = requests.get(
            f"{GITHUB_API}/users/{GITHUB_USERNAME}/events/public",
            headers=github_headers(),
            params={"per_page": 100},
            timeout=15,
        )
        if resp.status_code == 200:
            events = resp.json()
            unique_days = set()
            for event in events:
                if event.get("type") in ("PushEvent", "CreateEvent", "IssuesEvent", "PullRequestEvent"):
                    date_str = event.get("created_at", "")
                    if date_str:
                        day = date_str[:10]
                        unique_days.add(day)
            stats["active_days"] = len(unique_days)
    except Exception:
        pass

    return stats


def get_top_languages(languages, n=3):
    """Return top N languages sorted by usage."""
    sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
    return [lang for lang, _ in sorted_langs[:n]]


def calculate_years_active(first_year):
    """Calculate years active since first commit."""
    if first_year is None:
        return None
    current_year = datetime.now(timezone.utc).year
    years = current_year - first_year
    return max(years, 1)


def get_tech_stats():
    """Gather dynamic stats from the repo to reflect code changes."""
    # Count total Python/JS/TS files as a proxy for code activity
    file_counts = {"py": 0, "js": 0, "ts": 0, "sol": 0}
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__"}]
        for f in files:
            ext = f.rsplit(".", 1)[-1].lower() if "." in f else ""
            if ext in file_counts:
                file_counts[ext] += 1
    return file_counts


def update_readme(image_data, file_counts, github_stats):
    """Replace image block, stats, and GitHub data in README."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    image_url = image_data["urls"]["regular"]
    photo_link = image_data["links"]["html"]
    photographer = image_data["user"]["name"]

    new_block = (
        f"![Hero]({image_url}?auto=format&fit=crop&w=1200&q=80)\n\n"
        f"<sub>Today's image: <a href=\"{photo_link}\">{photographer}</a> "
        f"on Unsplash · Updated {today}</sub>"
    )

    # Replace everything between <!-- HERO:START --> and <!-- HERO:END -->
    pattern = r"<!-- HERO:START -->.*?<!-- HERO:END -->"
    replacement = f"<!-- HERO:START -->\n{new_block}\n<!-- HERO:END -->"

    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    else:
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("# "):
                insert_idx = i + 1
                break
        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, "<!-- HERO:START -->")
        lines.insert(insert_idx + 2, new_block)
        lines.insert(insert_idx + 3, "<!-- HERO:END -->")
        lines.insert(insert_idx + 4, "")
        content = "\n".join(lines)

    # Update code stats comment
    stats_line = (
        f"<!-- CODE_STATS:START -->"
        f" *Code footprint: {file_counts['py']} Python · "
        f"{file_counts['js']} JS · {file_counts['ts']} TS · "
        f"{file_counts['sol']} Solidity*"
        f" <!-- CODE_STATS:END -->"
    )

    stats_pattern = r"<!-- CODE_STATS:START -->.*?<!-- CODE_STATS:END -->"
    if re.search(stats_pattern, content, re.DOTALL):
        content = re.sub(stats_pattern, stats_line, content, flags=re.DOTALL)
    else:
        content = content.rstrip() + "\n\n" + stats_line + "\n"

    # Update GitHub profile stats
    top_langs = get_top_languages(github_stats["languages"])
    years_active = calculate_years_active(github_stats["first_commit_year"])
    years_str = f"{years_active}+" if years_active else "1+"
    repos_str = str(github_stats["repos"])
    stars_str = str(github_stats["stars"])
    followers_str = str(github_stats["followers"])
    lang_str = " · ".join(top_langs) if top_langs else "Multi-language"

    gh_stats_line = (
        f"<!-- GITHUB_STATS:START -->\n"
        f"**{years_str} years shipping 0→1 products · {repos_str} repos · "
        f"{stars_str} stars · {followers_str} followers**\n"
        f"*Primary: {lang_str}* · Updated {today}\n"
        f"<!-- GITHUB_STATS:END -->"
    )

    gh_pattern = r"<!-- GITHUB_STATS:START -->.*?<!-- GITHUB_STATS:END -->"
    if re.search(gh_pattern, content, re.DOTALL):
        content = re.sub(gh_pattern, gh_stats_line, content, flags=re.DOTALL)
    else:
        # Insert after the heading line
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("**") and "shipping" in line:
                lines[i] = gh_stats_line
                content = "\n".join(lines)
                break

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    file_counts = get_tech_stats()
    github_stats = fetch_github_stats()

    if not UNSPLASH_ACCESS_KEY:
        print("Warning: UNSPLASH_ACCESS_KEY not set, skipping image update")
        with open(README_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        stats_line = (
            f"<!-- CODE_STATS:START -->"
            f" *Code footprint: {file_counts['py']} Python · "
            f"{file_counts['js']} JS · {file_counts['ts']} TS · "
            f"{file_counts['sol']} Solidity*"
            f" <!-- CODE_STATS:END -->"
        )
        stats_pattern = r"<!-- CODE_STATS:START -->.*?<!-- CODE_STATS:END -->"
        if re.search(stats_pattern, content, re.DOTALL):
            content = re.sub(stats_pattern, stats_line, content, flags=re.DOTALL)
        else:
            content = content.rstrip() + "\n\n" + stats_line + "\n"
        with open(README_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        return

    history = load_history()
    image_data = get_unique_image(history)
    save_history(image_data["id"], history)

    update_readme(image_data, file_counts, github_stats)

    print(f"Updated README with image {image_data['id']} by {image_data['user']['name']}")
    print(f"GitHub stats: {github_stats['repos']} repos, {github_stats['stars']} stars, {github_stats['followers']} followers")


if __name__ == "__main__":
    main()
