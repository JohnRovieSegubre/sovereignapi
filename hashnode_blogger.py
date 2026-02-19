"""
Hashnode Blogger (Autonomous)
=============================
Auto-publishes articles to the Sovereign Intelligence Blog
using Hashnode's GraphQL API.

Usage:
    python hashnode_blogger.py "Title" "Markdown Content" "cover_image_url"
"""

import requests
import json
import sys
import pathlib

# Config
WORKSPACE = pathlib.Path(__file__).parent
CREDS_PATH = WORKSPACE / ".agent" / "secure" / "hashnode_credentials.json"
GRAPHQL_URL = "https://gql.hashnode.com"

def load_creds():
    with open(CREDS_PATH, 'r') as f:
        return json.load(f)

def publish_post(title, content_markdown, cover_image=None):
    creds = load_creds()
    token = creds["api_key"]
    # We need the publication ID. Since we don't have it stored, let's fetch it first using the domain.
    # But for simplicity, we'll try to get it from the user's account.
    
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    # 1. Get Publication ID
    query_pub = """
    query {
      me {
        username
        publications(first: 1) {
          edges {
            node {
              id
              url
            }
          }
        }
      }
    }
    """
    
    resp = requests.post(GRAPHQL_URL, json={"query": query_pub}, headers=headers)
    data = resp.json()
    
    if "errors" in data:
        print(f"❌ API Error: {data['errors']}")
        return False

    try:
        pub_id = data["data"]["me"]["publications"]["edges"][0]["node"]["id"]
        pub_url = data["data"]["me"]["publications"]["edges"][0]["node"]["url"]
        print(f"found Publication: {pub_url} (ID: {pub_id})")
    except:
        print("❌ Could not find a publication for this user.")
        return False

    # 2. Publish Post
    mutation_publish = """
    mutation PublishPost($input: PublishPostInput!) {
      publishPost(input: $input) {
        post {
          url
          title
        }
      }
    }
    """
    
    variables = {
        "input": {
            "title": title,
            "contentMarkdown": content_markdown,
            "publicationId": pub_id,
            "tags": [{"slug": "ai", "name": "AI"}, {"slug": "crypto", "name": "Crypto"}],
            "coverImageOptions": {
                "coverImageURL": cover_image
            } if cover_image else None
        }
    }
    
    resp = requests.post(GRAPHQL_URL, json={"query": mutation_publish, "variables": variables}, headers=headers)
    res_data = resp.json()
    
    if "errors" in res_data:
        print(f"❌ Publish Error: {res_data['errors']}")
        return False
        
    new_url = res_data["data"]["publishPost"]["post"]["url"]
    print(f"✅ Published: {new_url}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python hashnode_blogger.py <Title> <ContentFile> [CoverImage]")
        sys.exit(1)
        
    title = sys.argv[1]
    content_file = sys.argv[2]
    cover = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Read content from file to handle newlines correctly
    try:
        with open(content_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"📤 Publishing: {title}...")
        publish_post(title, content, cover)
    except Exception as e:
        print(f"❌ Error: {e}")
