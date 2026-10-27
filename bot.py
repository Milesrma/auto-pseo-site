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
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_db(pages):
    with open(DB_FILE, "w") as f:
        json.dump(pages, f, indent=2)

def scrape_live_demand():
    print("[*] Phase 1: Scraping live buyer-intent threads & search queries...")
    signals = []
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    
    # 1. Scrape live Reddit hardware/AI/rendering buyer questions
    subreddits = ["LocalLLaMA", "gpu", "homelab", "renderings", "StableDiffusion"]
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=15"
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                posts = r.json().get("data", {}).get("children", [])
                for p in posts:
                    d = p.get("data", {})
                    title = d.get("title", "")
                    permalink = "https://www.reddit.com" + d.get("permalink", "")
                    if any(w in title.lower() for w in ["vs", "cost", "worth", "buy", "rent", "vram", "gpu", "rtx", "gb", "run", "build", "price", "budget"]):
                        signals.append({"source": f"r/{sub}", "question": title, "url": permalink})
        except Exception:
            pass

    # 2. Scrape live Google Autocomplete buyer queries
    seed_queries = [
        "calculator for gpu ",
        "how much vram for ",
        "rtx 4090 vs ",
        "rtx 5090 vs ",
        "cloud gpu cost for ",
        "cheapest gpu to run "
    ]
    for q in seed_queries:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&q={requests.utils.quote(q)}"
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                suggestions = r.json()[1]
                for s in suggestions[:3]:
                    signals.append({"source": "Google Live Search", "question": s, "url": f"https://www.google.com/search?q={requests.utils.quote(s)}"})
        except Exception:
            pass

    print(f"[+] Captured {len(signals)} live demand signals from Reddit & Google!")
    return signals[:30]

def generate_sniper_tools(existing_pages, signals, batch_size=10):
    existing_slugs = [p["slug"] for p in existing_pages]
    print(f"[*] Phase 2: Designing {batch_size} High-Converting Custom Calculators from live demand...")

    prompt = f"""
    You are an elite conversion-focused engineer. Below are LIVE questions and search queries scraped right now from Reddit and Google:
    {json.dumps(signals, indent=2)}

    Pick the {batch_size} highest-intent hardware/cloud-compute/AI problems where the user has their wallet out (deciding what GPU to buy on Amazon vs renting on RunPod).
    Do NOT use any of these existing slugs: {json.dumps(existing_slugs)}

    Return a JSON object with a single key "pages" containing an array of {batch_size} objects.
    Each object MUST have:
    - "slug": SEO URL string (e.g., "llama-3-70b-vram-and-gpu-cost-calculator")
    - "title": High-CTR SEO Title solving the exact problem
    - "source_url": The exact URL from the scraped signals that inspired this tool
    - "source_question": The exact question/title from the scraped signals
    - "item_a": Best Local Hardware to buy for this (e.g., "Dual RTX 3090 48GB Rig" or "RTX 4090 24GB")
    - "item_b": Best Cloud GPU to rent for this (e.g., "RunPod NVIDIA A100 80GB")
    - "hw_upfront_cost": Float (Upfront purchase price in USD of item_a, e.g., 1850.0)
    - "cost_a_per_hr": Float (Electricity cost per hour in USD to run item_a locally, e.g., 0.08)
    - "cost_b_per_hr": Float (Hourly cloud rental cost in USD for item_b, e.g., 1.19)
    - "speed_multiplier": Float (How much faster item_b is than item_a, e.g., 1.8)
    - "vram_gb_needed": Integer (Recommended VRAM in GB for this workload, e.g., 48)
    - "verdict": 2-sentence sharp financial breakdown explaining the exact break-even hours between buying local hardware on Amazon vs renting on RunPod.
    - "affiliate_query": High-converting Amazon search string for buying item_a (e.g., "NVIDIA GeForce RTX 4090 24GB GDDR6X")
    - "reddit_reply": A helpful, non-spammy 2-sentence reply answering the user's question with real numbers and mentioning the free break-even calculator link.
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
                        temperature=0.4
                    )
                )
                data = json.loads(response.text)
                new_items = data.get("pages", [])
                print(f"[+] Success with {model}! Built {len(new_items)} sniper tools.")
                return new_items
            except Exception as e:
                print(f"[!] {model} busy ({e}). Switching...")
                time.sleep(2)
        time.sleep(5)

def build_files(all_pages, newest_pages):
    print(f"[*] Phase 3: Compiling {len(all_pages)} interactive break-even calculators & MONEY_RADAR.md...")
    files_to_commit = []
    links_html = ""
    base_url = f"https://{GITHUB_USERNAME.lower()}.github.io/{REPO_NAME}"

    for page in reversed(all_pages):
        slug = page["slug"]
        filename = f"{slug}.html"
        query_encoded = page.get("affiliate_query", page["item_a"]).replace(" ", "+")
        affiliate_url = f"https://www.amazon.com/s?k={query_encoded}&tag={AMAZON_TAG}"

        upfront = page.get("hw_upfront_cost", 1600.0)
        vram = page.get("vram_gb_needed", 24)
        rate_a = page.get("cost_a_per_hr", 0.09)
        rate_b = page.get("cost_b_per_hr", 0.89)
        mult = page.get("speed_multiplier", 1.5)

        links_html += f"""
        <a href="{filename}" class="block p-5 bg-zinc-900 border border-zinc-800 rounded-xl hover:border-emerald-500 transition">
            <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-mono uppercase px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded">Min VRAM: {vram}GB</span>
                <span class="text-xs text-zinc-500">Break-Even Tool &rarr;</span>
            </div>
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
    <div class="max-w-4xl mx-auto">
        <a href="index.html" class="text-xs uppercase tracking-widest text-emerald-400 hover:underline">&larr; All Hardware &amp; Cloud Break-Even Tools</a>
        <div class="mt-4 flex flex-wrap gap-2">
            <span class="text-xs font-mono px-2.5 py-1 bg-zinc-900 border border-zinc-800 rounded text-emerald-400">Target VRAM: {vram} GB</span>
            <span class="text-xs font-mono px-2.5 py-1 bg-zinc-900 border border-zinc-800 rounded text-zinc-300">Local Hardware Est: ${upfront}</span>
        </div>
        <h1 class="text-3xl md:text-4xl font-bold mt-3 mb-3">{page["title"]}</h1>
        <p class="text-zinc-400 mb-8 leading-relaxed">{page["verdict"]}</p>

        <div class="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-8">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div>
                    <label class="block text-sm font-medium text-zinc-300 mb-2">
                        Usage Hours Per Month: <span id="hrsVal" class="text-emerald-400 font-bold">120</span> hrs/mo
                    </label>
                    <input id="hrsSlider" type="range" min="10" max="720" value="120" class="w-full accent-emerald-500 cursor-pointer">
                </div>
                <div>
                    <label class="block text-sm font-medium text-zinc-300 mb-2">
                        Time Horizon (Months): <span id="moVal" class="text-emerald-400 font-bold">6</span> months
                    </label>
                    <input id="moSlider" type="range" min="1" max="36" value="6" class="w-full accent-emerald-500 cursor-pointer">
                </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="p-5 bg-zinc-950 rounded-lg border border-zinc-800">
                    <div class="text-xs text-zinc-500 uppercase tracking-wider">Buy Local: {page["item_a"]}</div>
                    <div id="costA" class="text-3xl font-bold text-white mt-2">$0.00</div>
                    <div class="text-xs text-zinc-500 mt-1">Includes ${upfront} hardware + ${rate_a}/hr power</div>
                </div>
                <div class="p-5 bg-zinc-950 rounded-lg border border-emerald-900/60">
                    <div class="text-xs text-emerald-400 uppercase tracking-wider">Rent Cloud: {page["item_b"]}</div>
                    <div id="costB" class="text-3xl font-bold text-emerald-400 mt-2">$0.00</div>
                    <div class="text-xs text-zinc-500 mt-1">$0 upfront &bull; {mult}x speed (${rate_b}/hr)</div>
                </div>
                <div class="p-5 bg-zinc-950 rounded-lg border border-zinc-800 flex flex-col justify-center">
                    <div class="text-xs text-zinc-500 uppercase tracking-wider">Winner for Your Workload</div>
                    <div id="winnerText" class="text-xl font-bold text-amber-400 mt-2">Calculating...</div>
                    <div id="savingsText" class="text-xs text-zinc-400 mt-1"></div>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="p-6 bg-zinc-900/80 border border-zinc-800 rounded-xl flex flex-col justify-between gap-4">
                <div>
                    <span class="text-xs uppercase font-bold tracking-wider text-emerald-400">Option 1: Own The Hardware</span>
                    <h3 class="font-bold text-lg text-white mt-1">Buy {page["item_a"]}</h3>
                    <p class="text-sm text-zinc-400 mt-1">Best if you run heavy workloads every day and want full local privacy + resale value.</p>
                </div>
                <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored"
                   class="text-center bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold px-5 py-3 rounded-lg transition">
                   Check Amazon Price &amp; Stock &rarr;
                </a>
            </div>

            <div class="p-6 bg-zinc-900/80 border border-zinc-800 rounded-xl flex flex-col justify-between gap-4">
                <div>
                    <span class="text-xs uppercase font-bold tracking-wider text-amber-400">Option 2: Zero Upfront Cost</span>
                    <h3 class="font-bold text-lg text-white mt-1">Rent {page["item_b"]} Instantly</h3>
                    <p class="text-sm text-zinc-400 mt-1">Skip the ${upfront} upfront hardware bill. Spin up {vram}GB+ VRAM in 30 seconds and pay by the minute.</p>
                </div>
                <a href="{RUNPOD_LINK}" target="_blank" rel="nofollow sponsored"
                   class="text-center bg-zinc-100 hover:bg-white text-zinc-950 font-bold px-5 py-3 rounded-lg transition">
                   Deploy on RunPod Now &rarr;
                </a>
            </div>
        </div>
    </div>

    <script>
        const hrsSlider = document.getElementById('hrsSlider'), moSlider = document.getElementById('moSlider');
        const hrsVal = document.getElementById('hrsVal'), moVal = document.getElementById('moVal');
        const costA = document.getElementById('costA'), costB = document.getElementById('costB');
        const winnerText = document.getElementById('winnerText'), savingsText = document.getElementById('savingsText');
        const upfront = {upfront}, rateA = {rate_a}, rateB = {rate_b}, mult = {mult};

        function calc() {{
            let h = parseFloat(hrsSlider.value), m = parseFloat(moSlider.value);
            hrsVal.innerText = h; moVal.innerText = m;
            let totalLocal = upfront + (h * m * rateA);
            let totalCloud = (h / mult) * m * rateB;
            costA.innerText = '$' + totalLocal.toFixed(0);
            costB.innerText = '$' + totalCloud.toFixed(0);
            if (totalCloud < totalLocal) {{
                winnerText.innerText = 'Rent on Cloud (RunPod)';
                winnerText.className = 'text-xl font-bold text-emerald-400 mt-2';
                savingsText.innerText = 'Saves you $' + (totalLocal - totalCloud).toFixed(0) + ' over ' + m + ' mo';
            }} else {{
                winnerText.innerText = 'Buy Local Hardware';
                winnerText.className = 'text-xl font-bold text-amber-400 mt-2';
                savingsText.innerText = 'Saves you $' + (totalCloud - totalLocal).toFixed(0) + ' over ' + m + ' mo';
            }}
        }}
        hrsSlider.addEventListener('input', calc);
        moSlider.addEventListener('input', calc);
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
    <title>AI Hardware vs Cloud GPU Break-Even Calculators</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-zinc-100 p-6 md:p-12">
    <div class="max-w-4xl mx-auto">
        <h1 class="text-4xl font-bold mb-2">Buy Local GPU vs. Rent Cloud Break-Even Tools</h1>
        <p class="text-zinc-400 mb-8">Real-time VRAM, electricity, and hardware amortization calculators ({len(all_pages)} active tools).</p>
        <div class="grid md:grid-cols-2 gap-4">{links_html}</div>
    </div>
</body>
</html>"""
    files_to_commit.append({"path": "index.html", "content": index_html})

    # Build MONEY_RADAR.md so the user can get instant Day-1 clicks from live Reddit threads
    radar_md = "# 🎯 LIVE MONEY RADAR (Instant Traffic Opportunities)\n\n"
    radar_md += "These tools were built directly from **live questions people asked today**. Click a thread below and paste the ready-made reply to get instant buyer clicks:\n\n"
    for np in newest_pages:
        tool_url = f"{base_url}/{np['slug']}.html"
        radar_md += f"### 🔥 Question: \"{np.get('source_question', np['title'])}\"\n"
        radar_md += f"- **Where they asked:** {np.get('source_url', 'Google Search')}\n"
        radar_md += f"- **Your Custom Tool Link:** {tool_url}\n"
        radar_md += f"- **Copy-Paste Reply:**\n> {np.get('reddit_reply', '')} {tool_url}\n\n---\n\n"

    files_to_commit.append({"path": "MONEY_RADAR.md", "content": radar_md})

    sitemap_items = "".join([f"<url><loc>{base_url}/{p['slug']}.html</loc></url>" for p in all_pages])
    sitemap_xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{base_url}/</loc></url>{sitemap_items}</urlset>'
    files_to_commit.append({"path": "sitemap.xml", "content": sitemap_xml})
    files_to_commit.append({"path": "database.json", "content": json.dumps(all_pages, indent=2)})

    return files_to_commit

def push_to_github(files):
    print("[*] Phase 4: Pushing sniper tools & MONEY_RADAR.md to GitHub...")
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
        payload = {"message": f"Sniper update: {path}", "content": encoded_content}
        if get_file.status_code == 200:
            payload["sha"] = get_file.json()["sha"]

        put_res = requests.put(url, headers=headers, json=payload)
        if put_res.status_code in (200, 201):
            print(f"  [ok] Synced: {path}")

    # Also upload the upgraded bot.py itself so the nightly GitHub Action runs this new version
    with open("bot.py", "r") as bf:
        bot_encoded = base64.b64encode(bf.read().encode("utf-8")).decode("utf-8")
    b_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/bot.py"
    b_get = requests.get(b_url, headers=headers)
    b_payload = {"message": "Upgrade bot.py to Live Demand Scraper", "content": bot_encoded}
    if b_get.status_code == 200:
        b_payload["sha"] = b_get.json()["sha"]
    requests.put(b_url, headers=headers, json=b_payload)
    print("  [ok] Upgraded cloud bot.py for nightly runs!")

    print("\n==========================================")
    print(f"DONE! Check your live Money Radar leads at:")
    print(f"https://github.com/{GITHUB_USERNAME}/{REPO_NAME}/blob/main/MONEY_RADAR.md")
    print("==========================================")

if __name__ == "__main__":
    db = load_existing_db()
    signals = scrape_live_demand()
    new_pages = generate_sniper_tools(db, signals, batch_size=10)
    
    existing_slugs = {p["slug"] for p in db}
    added = []
    for np in new_pages:
        if np["slug"] not in existing_slugs:
            db.append(np)
            added.append(np)
            
    save_db(db)
    # Only re-upload the new pages + index + radar + sitemap + database so it finishes 5x faster!
    all_files = build_files(db, added)
    new_slugs_files = {f"{p['slug']}.html" for p in added} | {"index.html", "MONEY_RADAR.md", "sitemap.xml", "database.json"}
    fast_files = [f for f in all_files if f["path"] in new_slugs_files]
    push_to_github(fast_files)
