import requests
import os
from datetime import datetime
from notion_client import Client

CONFIG = {
    "WEREAD_COOKIE": f"wr_skey={os.getenv('WR_SKEY')}; wr_vid={os.getenv('WR_VID')}",
    "NOTION_TOKEN": os.getenv("NOTION_TOKEN"),
    "NOTION_DATABASE_ID": os.getenv("NOTION_DATABASE_ID")
}

def validate_cookie(cookie):
    required = {'wr_skey', 'wr_vid'}
    present = {k.split('=')[0] for k in cookie.split(';') if k.strip()}
    if not required.issubset(present):
        raise ValueError(f"Missing required fields: {required}")

def get_weread_highlights():
    validate_cookie(CONFIG["WEREAD_COOKIE"])
    url = "https://i.weread.qq.com/user/notebooks"
    headers = {
        "Cookie": CONFIG["WEREAD_COOKIE"],
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://weread.qq.com/"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 401:
            if "LOGIN ERR" in response.text:
                print("Check: 1. Cookie expiry 2. Enterprise WeChat login")
        response.raise_for_status()
        return process_books(response.json())
    
    except Exception as e:
        print(f"Failed to get highlights: {str(e)}")
        return []

def process_books(data):
    highlights = []
    for book in data.get("books", []):
        notes_url = f"https://i.weread.qq.com/book/bookmarklist?bookId={book['bookId']}"
        notes_data = requests.get(
            notes_url, 
            headers={"Cookie": CONFIG["WEREAD_COOKIE"]}
        ).json()
        
        for chapter in notes_data.get("chapters", []):
            for mark in chapter.get("marks", []):
                highlights.append({
                    "book_id": book["bookId"],
                    "book_title": book["title"],
                    "author": book.get("author", ""),
                    "chapter": chapter.get("chapterTitle", ""),
                    "content": mark.get("markText", ""),
                    "create_time": datetime.fromtimestamp(mark.get("createTime", 0)).strftime("%Y-%m-%d %H:%M:%S"),
                    "range": mark.get("range", "")
                })
    return highlights

def sync_to_notion(highlights):
    notion = Client(auth=CONFIG["NOTION_TOKEN"])
    
    for highlight in highlights:
        content_prefix = highlight["content"][:20]
        query = {
            "filter": {
                "and": [
                    {"property": "Book ID", "rich_text": {"equals": highlight["book_id"]}},
                    {"property": "Content", "rich_text": {"contains": content_prefix}}
                ]
            }
        }
        
        existing = notion.databases.query(
            database_id=CONFIG["NOTION_DATABASE_ID"], 
            **query
        ).get("results", [])
        
        if not existing:
            create_notion_page(notion, highlight)

def create_notion_page(notion, highlight):
    new_page = {
        "parent": {"database_id": CONFIG["NOTION_DATABASE_ID"]},
        "properties": {
            "Book Title": {"title": [{"text": {"content": highlight["book_title"]}}]},
            "Author": {"rich_text": [{"text": {"content": highlight["author"]}}]},
            "Chapter": {"rich_text": [{"text": {"content": highlight["chapter"]}}]},
            "Content": {"rich_text": [{"text": {"content": highlight["content"]}}]},
            "Date": {"date": {"start": highlight["create_time"]}},
            "Book ID": {"rich_text": [{"text": {"content": highlight["book_id"]}}]},
            "Range": {"rich_text": [{"text": {"content": highlight["range"]}}]}
        }
    }
    try:
        notion.pages.create(**new_page)
        print(f"Added: {highlight['book_title'][:15]}...")
    except Exception as e:
        print(f"Notion error: {str(e)}")

def main():
    print("Starting WeRead to Notion sync")
    highlights = get_weread_highlights()
    if highlights:
        print(f"Found {len(highlights)} highlights")
        sync_to_notion(highlights)
    print("Sync completed")

if __name__ == "__main__":
    main()
