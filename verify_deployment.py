import requests
import sys

BASE_URL = "https://api.sovereign-api.com"

def test_registration():
    print(f"\n⚡ Testing Registration Endpoint ({BASE_URL}/v1/register)...")
    try:
        resp = requests.post(f"{BASE_URL}/v1/register", json={"name": "VerificationBot", "description": "Automated test"})
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Success! Created Agent: {data['agent_name']}")
            print(f"   API Key: {data['api_key']}")
            return True
        else:
            print(f"❌ Failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_skill_md():
    print(f"\n⚡ Verifying skill.md content...")
    try:
        resp = requests.get(f"{BASE_URL}/skill.md")
        if "Self-Register (Autonomous)" in resp.text:
            print("✅ Success! Found 'Self-Register (Autonomous)' in skill.md")
            return True
        else:
            print("❌ Failed: 'Self-Register (Autonomous)' not found in skill.md")
            print(f"Snippet: {resp.text[:200]}...")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_landing_page():
    print(f"\n⚡ Verifying Landing Page content...")
    try:
        resp = requests.get(f"{BASE_URL}/")
        if "curl -X POST" in resp.text and "/v1/register" in resp.text:
            print("✅ Success! Found register curl command in landing page")
            return True
        else:
            print("❌ Failed: Register curl command not found in landing page")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

if __name__ == "__main__":
    r1 = test_registration()
    r2 = test_skill_md()
    r3 = test_landing_page()
    
    if r1 and r2 and r3:
        print("\n✨ ALL SYSTEM CHECKS PASSED ✨")
        sys.exit(0)
    else:
        print("\n⚠️ SOME CHECKS FAILED")
        sys.exit(1)
