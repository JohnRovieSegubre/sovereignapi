import os
import shutil
import re

# Paths
SOURCE_DIR = "temp_awesome_skills/skills"
TARGET_DIR = ".agent/skills"

# Category Mapping Rules (Regex -> Prefix)
# Priority matters! First match wins.
CATEGORY_RULES = [
    # 🛡️ Security (Red Team & Blue Team)
    (r"(pentest|exploit|metasploit|hack|attack|vulnerability|scanner|privilege|fuzz|red-team|bloodhound)", "sec-redteam-"),
    (r"(owasp|xss|injection|idor|auth-testing|security|audit|threat|defense)", "sec-psirt-"),
    
    # 📈 Growth & Marketing
    (r"(seo|keyword|serp|ranking|audit-site)", "growth-seo-"),
    (r"(social|twitter|linkedin|instagram|viral|audience)", "growth-social-"),
    (r"(copy|email|content|blog|newsletter|brand|voice)", "growth-content-"),
    (r"(launch|product-hunt|startup|business|monetization|pricing)", "growth-biz-"),
    
    # 🔌 APIs & Integrations
    (r"(stripe|payment|billing|firebase|supabase|discord|slack|twilio|hubspot|notion|google|aws|azure|gcp)", "api-int-"),
    
    # 🛸 Autonomous & AI Agents
    (r"(loki|autonomous|agent|planner|orchestrat|memory|reflection|subagent)", "auto-agent-"),
    
    # 🛠️ Development - Frontend
    (r"(react|vue|angular|svelte|css|tailwind|ui|ux|frontend|component|design-system|canvas|animation)", "dev-frontend-"),
    
    # 🛠️ Development - Backend
    (r"(node|express|nest|python|django|flask|api|backend|database|sql|postgres|mongo|redis|graphql)", "dev-backend-"),
    
    # 🛠️ Development - DevOps
    (r"(docker|kube|cloud|deploy|ci-cd|git|linux|shell|bash|terminal|server)", "dev-ops-"),
    
    # 🧪 QA & Testing
    (r"(test|qa|playwright|selenium|cypress|debug|lint)", "dev-qa-"),
    
    # 🎮 Game Dev
    (r"(game|unity|godot|unreal|shader|3d)", "creative-game-"),
    
    # 📄 Docs
    (r"(doc|pdf|ppt|xls|csv|file)", "office-tools-")
]

# Ensure target directory exists
os.makedirs(TARGET_DIR, exist_ok=True)

def determine_new_name(original_name):
    """Determine the new name based on category rules."""
    for pattern, prefix in CATEGORY_RULES:
        if re.search(pattern, original_name, re.IGNORECASE):
            # If the name already starts with the prefix (unlikely but possible), don't double it
            if original_name.startswith(prefix):
               return original_name
            return f"{prefix}{original_name}"
    
    # Fallback category
    return f"general-{original_name}"

def install_skills():
    print(f"🚀 Starting installation from {SOURCE_DIR} to {TARGET_DIR}...")
    
    if not os.path.exists(SOURCE_DIR):
        print(f"❌ Source directory not found: {SOURCE_DIR}")
        return

    skills_installed = 0
    
    for skill_name in os.listdir(SOURCE_DIR):
        src_path = os.path.join(SOURCE_DIR, skill_name)
        
        # Skip weird files, just want folders
        if not os.path.isdir(src_path):
            continue
            
        new_name = determine_new_name(skill_name)
        dest_path = os.path.join(TARGET_DIR, new_name)
        
        print(f"Installing {skill_name} -> {new_name}...")
        
        # 1. Copy Folder
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path) # Overwrite if exists
        shutil.copytree(src_path, dest_path)
        
        # 2. Update SKILL.md frontmatter
        skill_md_path = os.path.join(dest_path, "SKILL.md")
        if os.path.exists(skill_md_path):
            try:
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Regex to replace 'name: old-name' with 'name: new-name'
                # Only replaces the first occurrence (which is the frontmatter)
                new_content = re.sub(r"^name:\s*.*$", f"name: {new_name}", content, count=1, flags=re.MULTILINE)
                
                with open(skill_md_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                    
            except Exception as e:
                print(f"⚠️ Warning: Could not patch SKILL.md for {new_name}: {e}")
        
        skills_installed += 1

    print(f"\n✅ Installation Complete! Installed {skills_installed} skills.")

if __name__ == "__main__":
    install_skills()
