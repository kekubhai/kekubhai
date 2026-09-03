import os
import re
import random
import requests
from datetime import datetime, timezone


UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
README_PATH = "README.md"
HISTORY_FILE = ".github/image_history.txt"
QUERY = "technology landscape coding workspace"


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


def update_readme(image_data, file_counts):
    """Replace image block and stats in README."""
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
        # Insert after the first heading if markers don't exist
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
        # Append at the end
        content = content.rstrip() + "\n\n" + stats_line + "\n"

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    if not UNSPLASH_ACCESS_KEY:
        print("Warning: UNSPLASH_ACCESS_KEY not set, skipping image update")
        # Still update stats
        file_counts = get_tech_stats()
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

    file_counts = get_tech_stats()
    update_readme(image_data, file_counts)

    print(f"Updated README with image {image_data['id']} by {image_data['user']['name']}")


if __name__ == "__main__":
    main()
