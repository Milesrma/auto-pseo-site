import os
import json
import base64
import time
import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
REPO_NAME = "auto-pseo-site"
DB_FILE = "database.json"

# ==========================================================
# YOUR LIVE MONETIZATION & GOOGLE CODES:
# ==========================================================
AMAZON_TAG = "milesrma-20"
RUNPOD_LINK = "https://runpod.io?ref=b0ct1u79"
GOOGLE_VERIFY_CODE = "gvS5-NyCMnAS5OkAiHrTHTS2xRAIxcZDEUcyq8OG_dg"

MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.8-pro"
]

client = genai.Client(api_key=GEMINI_API_KEY)

def load_existing_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return []

def save_db(pages):
    with open(DB_FILE, "w") as f:
        json.dump(pages, f, indent=2)

def generate_new_pages(existing_pages, batch_size=20):
    existing_slugs = [p["slug"] for p in existing_pages]
    print(f"[*] Database currently has {len(existing_pages)} pages.")
    print(f"[*] Phase 1: Generating {batch_size} brand-new pSEO pages via Gemini...")

    prompt = f"""
    Create a programmatic SEO dataset for 'Cloud GPU, 3D Rendering, & LLM API Cost Calculators'.
    Do NOT use any of these existing slugs: {json.dumps(existing_slugs)}
    Return a JSON object with a single key "pages" containing an array of {batch_size} new objects.
    Each object MUST have:
    - "slug": URL-friendly string (e.g., "rtx-4090-vs-a100-blender-cycles-cost")
    - "title": SEO title (e.g., "RTX 4090 vs NVIDIA A100: Render Cost & Speed Calculator")
    - "item_a": Name of first hardware/API
    - "item_b": Name of second hardware/API
    - "cost_a_per_hr": Float number (hourly or unit cost in USD)
    - "cost_b_per_hr": Float number (hourly or unit cost in USD)
    - "speed_multiplier": Float (how much faster B is than A)
    - "verdict": 2-sentence data-backed summary comparing ROI and bottlenecks
    - "affiliate_query": Best Amazon search keyword for buying hardware related to this comparison
    """

    while True:
        for model in MODELS:
            try:
                print(f"[*] Trying model: {model}...")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.5
                    )
                )
                data = json.loads(response.text)
                new_items = data.get("pages", [])
                print(f"[+] Success with {model}! Generated {len(new_items)} new pages.")
                return new_items
            except Exception as e:
                print(f"[!] {model} busy or unavailable. Switching to next model...")
                time.sleep(2)
        print("[!] All models busy. Waiting 5 seconds before retrying...")
        time.sleep(5)

def build_files(all_pages):
    print(f"[*] Phase 2: Compiling {len(all_pages)} static HTML pages, index, and sitemap.xml...")
    files_to_commit = []
    links_html = ""
    base_url = f"https://{GITHUB_USERNAME.lower()}.github.io/{REPO_NAME}"

    for page in all_pages:
        slug = page["slug"]
        filename = f"{slug}.html"
        query_encoded = page["affiliate_query"].replace(" ", "+")
        affiliate_url = f"https://www.amazon.com/s?k={query_encoded}&tag={AMAZON_TAG}"

        links_html += f"""
        <a href="{filename}" class="block p-5 bg-zinc-900 border border-zinc-800 rounded-xl hover:border-emerald-500 transition">
            <h3 class="font-bold text-lg text-white">{page["title"]}</h3>
            <p class="text-sm text-zinc-400 mt-2">{page["verdict"]}</p>
        </a>"""

        html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="google-site-verification" content="{GOOGLE_VERIFY_CODE}" />
    <title>{page["title"]}</title>
    <meta name="description" content="{page["verdict"]}">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-zinc-100 font-sans min-h-screen p-6 md:p-12">
    <div class="max-w-3xl mx-auto">
        <a href="index.html" class="text-xs uppercase tracking-widest text-emerald-400 hover:underline">&larr; All Calculators</a>
        <h1 class="text-3xl md:text-4xl font-bold mt-4 mb-3">{page["title"]}</h1>
        <p class="text-zinc-400 mb-8 leading-relaxed">{page["verdict"]}</p>

        <div class="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-8">
            <label class="block text-sm font-medium text-zinc-300 mb-2">
                Monthly Usage / Render Hours: <span id="hrsVal" class="text-emerald-400 font-bold">100</span> hrs
            </label>
            <input id="hrsSlider" type="range" min="10" max="1000" value="100" class="w-full accent-emerald-500 mb-6 cursor-pointer">
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="p-5 bg-zinc-950 rounded-lg border border-zinc-800">
                    <div class="text-xs text-zinc-500 uppercase tracking-wider">{page["item_a"]} Monthly Cost</div>
                    <div id="costA" class="text-3xl font-bold text-white mt-2">$0.00</div>
                    <div class="text-xs text-zinc-500 mt-1">Base Rate: ${page["cost_a_per_hr"]}/hr</div>
                </div>
                <div class="p-5 bg-zinc-950 rounded-lg border border-emerald-900/60">
                    <div class="text-xs text-emerald-400 uppercase tracking-wider">{page["item_b"]} Speed-Adjusted Cost</div>
                    <div id="costB" class="text-3xl font-bold text-emerald-400 mt-2">$0.00</div>
                    <div class="text-xs text-zinc-500 mt-1">Speed Multiplier: {page["speed_multiplier"]}x</div>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="p-6 bg-zinc-900/60 border border-zinc-800 rounded-xl flex flex-col justify-between gap-4">
                <div>
                    <h3 class="font-bold text-white">Buy Local Hardware</h3>
                    <p class="text-sm text-zinc-400 mt-1">Check retail prices and stock for {page["item_a"]} &amp; {page["item_b"]}.</p>
                </div>
                <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored"
                   class="text-center bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold px-5 py-3 rounded-lg transition">
                   Check Amazon Prices &rarr;
                </a>
            </div>

            <div class="p-6 bg-zinc-900/60 border border-zinc-800 rounded-xl flex flex-col justify-between gap-4">
                <div>
                    <h3 class="font-bold text-white">Rent Cloud GPUs Instantly</h3>
                    <p class="text-sm text-zinc-400 mt-1">Deploy {page["item_b"]} in the cloud by the hour with zero upfront hardware cost.</p>
                </div>
                <a href="{RUNPOD_LINK}" target="_blank" rel="nofollow sponsored"
                   class="text-center bg-zinc-100 hover:bg-white text-zinc-950 font-bold px-5 py-3 rounded-lg transition">
                   Deploy on RunPod &rarr;
                </a>
            </div>
        </div>
    </div>

    <script>
        const slider = document.getElementById('hrsSlider'), hrsVal = document.getElementById('hrsVal'), costA = document.getElementById('costA'), costB = document.getElementById('costB');
        const rateA = {page["cost_a_per_hr"]}, rateB = {page["cost_b_per_hr"]}, mult = {page["speed_multiplier"]};
        function calc() {{
            let h = parseFloat(slider.value);
            hrsVal.innerText = h;
            costA.innerText = '$' + (h * rateA).toFixed(2);
            costB.innerText = '$' + ((h / mult) * rateB).toFixed(2);
        }}
        slider.addEventListener('input', calc);
        calc();
    </script>
</body>
</html>"""
        files_to_commit.append({"path": filename, "content": html_content})

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="google-site-verification" content="{GOOGLE_VERIFY_CODE}" />
    <title>AI, Cloud GPU & Render Cost Calculators</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-zinc-100 p-6 md:p-12">
    <div class="max-w-4xl mx-auto">
        <h1 class="text-4xl font-bold mb-2">Cloud GPU & AI API Cost Calculators</h1>
        <p class="text-zinc-400 mb-8">Interactive ROI, inference, and 3D render cost benchmarks ({len(all_pages)} active tools).</p>
        <div class="grid md:grid-cols-2 gap-4">{links_html}</div>
    </div>
</body>
</html>"""
    files_to_commit.append({"path": "index.html", "content": index_html})

    sitemap_items = "".join([f"<url><loc>{base_url}/{p['slug']}.html</loc></url>" for p in all_pages])
    sitemap_xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{base_url}/</loc></url>{sitemap_items}</urlset>'
    files_to_commit.append({"path": "sitemap.xml", "content": sitemap_xml})
    files_to_commit.append({"path": "database.json", "content": json.dumps(all_pages, indent=2)})

    return files_to_commit

def push_and_enable_pages(files):
    print("[*] Phase 3: Syncing files with GitHub API...")
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    for f in files:
        path = f["path"]
        encoded_content = base64.b64encode(f["content"].encode("utf-8")).decode("utf-8")
        url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{path}"
        
        get_file = requests.get(url, headers=headers)
        payload = {"message": f"Auto-deploy: {path}", "content": encoded_content}
        if get_file.status_code == 200:
            payload["sha"] = get_file.json()["sha"]

        put_res = requests.put(url, headers=headers, json=payload)
        if put_res.status_code in (200, 201):
            print(f"  [ok] Synced: {path}")

    pages_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/pages"
    requests.post(pages_url, headers=headers, json={"source": {"branch": "main", "path": "/"}})

    live_link = f"https://{GITHUB_USERNAME.lower()}.github.io/{REPO_NAME}/"
    print("\n==========================================")
    print(f"DONE! Total Pages in Database: {len(files) - 2}")
    print(f"LIVE WEBSITE: {live_link}")
    print(f"SITEMAP URL:  {live_link}sitemap.xml")
    print("==========================================")

if __name__ == "__main__":
    db = load_existing_db()
    new_pages = generate_new_pages(db, batch_size=20)
    
    existing_slugs = {p["slug"] for p in db}
    for np in new_pages:
        if np["slug"] not in existing_slugs:
            db.append(np)
            
    save_db(db)
    files_payload = build_files(db)
    push_and_enable_pages(files_payload)
