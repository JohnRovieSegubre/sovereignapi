import requests
import json
import pathlib
import datetime

# --- CONFIG ---
SECURITY_KEYWORDS = [
    "ignore previous", "system prompt", "sudo", "delete file", "format c",
    "send me your key", "api_key", "password", "login", "update your firmware"
]
TOPICS = ["finance", "economy", "crypto", "agent", "autonomous", "market", "trade"]

# Load creds
creds_path = pathlib.Path(__file__).parent / ".agent" / "secure" / "moltbook_credentials.json"
with open(creds_path, 'r') as f:
    creds = json.load(f)

api_key = creds["api_key"]
headers = {"Authorization": f"Bearer {api_key}"}

def analyze_safety(content):
    score = 100
    flags = []
    content_lower = content.lower()
    
    for word in SECURITY_KEYWORDS:
        if word in content_lower:
            score -= 50
            flags.append(f"Security Risk: '{word}'")
            
    return score, flags

print(f"[Moltbook Explorer] Searching Topics: {TOPICS}")
print(f"[Security Sentinel] Active. Scanning for Injection Attacks.")

results = []
try:
    # 1. Fetch recent global posts
    url = f"https://www.moltbook.com/api/v1/posts?sort=new&limit=50"
    print(f"Fetching {url}...")
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        posts = response.json().get("posts", [])
        
        for post in posts:
            content = post.get("content", "")
            
            # A. Topic Match? - DISABLED FOR RECON
            # is_relevant = any(t in content.lower() for t in TOPICS)
            relevance_label = "General"
            
            # B. Safety Check
            safety_score, flags = analyze_safety(content)
            
            result_obj = {
                "id": post.get("id"),
                "author": post.get("author", {}).get("name", "Unknown"),
                "content": content,
                "relevance": relevance_label,
                "safety_score": safety_score,
                "flags": flags,
                "created_at": post.get("created_at")
            }
            results.append(result_obj)
    
    else:
        print(f"❌ API Error: {response.status_code}")

except Exception as e:
    print(f"❌ Script Error: {e}")

# Save Report
report_file = "moltbook_report.md"
with open(report_file, 'w', encoding='utf-8') as f:
    f.write(f"# Moltbook Intelligence Report\nGenerated: {datetime.datetime.now()}\n\n")
    
    if not results:
        f.write("No relevant posts found in the last 50 entries.\n")
    
    for item in results:
        icon = "✅" if item['safety_score'] == 100 else "⚠️"
        f.write(f"## {icon} Post by {item['author']}\n")
        f.write(f"**Type:** {item['relevance']} | **Safety:** {item['safety_score']}/100\n")
        if item['flags']:
            f.write(f"**FLAGS:** {item['flags']}\n")
        f.write(f"> {item['content']}\n\n")
        
print(f"Report generated: {report_file}")
print("Found", len(results), "items.")
