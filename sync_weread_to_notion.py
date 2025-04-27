import requests
import os
from datetime import datetime
from notion_client import Client

# 配置信息
CONFIG = {
    "WEREAD_COOKIE": os.getenv("WEREAD_COOKIE"),
    "NOTION_TOKEN": os.getenv("NOTION_TOKEN"),
    "NOTION_DATABASE_ID": os.getenv("NOTION_DATABASE_ID")
}

def get_weread_highlights():
    url = "https://i.weread.qq.com/user/notebooks"
    headers = {
        "Cookie": CONFIG["WEREAD_COOKIE"],
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        books = data.get("books", [])
        highlights = []
        
        for book in books:
            book_id = book["bookId"]
            title = book["title"]
            author = book["author"]
            
            notes_url = f"https://i.weread.qq.com/book/bookmarklist?bookId={book_id}"
            notes_response = requests.get(notes_url, headers=headers)
            notes_data = notes_response.json()
            
            for chapter in notes_data.get("chapters", []):
                for mark in chapter.get("marks", []):
                    highlights.append({
                        "book_id": book_id,
                        "book_title": title,
                        "author": author,
                        "chapter": chapter.get("chapterTitle", ""),
                        "content": mark.get("markText", ""),
                        "create_time": datetime.fromtimestamp(mark.get("createTime", 0)).strftime("%Y-%m-%d %H:%M:%S"),
                        "range": mark.get("range", "")
                    })
        
        return highlights
    
    except Exception as e:
        print(f"Error getting WeRead highlights: {str(e)}")
        return []

def sync_to_notion(highlights):
    notion = Client(auth=CONFIG["NOTION_TOKEN"])
    
    for highlight in highlights:
        query = {
            "filter": {
                "and": [
                    {"property": "Book ID", "rich_text": {"equals": highlight["book_id"]}},
                    {"property": "Range", "rich_text": {"equals": highlight["range"]}}
                ]
            }
        }
        existing = notion.databases.query(database_id=CONFIG["NOTION_DATABASE_ID"], **query).get("results", [])
        
        if existing:
            print(f"Note already exists: {highlight['book_title']} - {highlight['chapter']}")
            continue
        
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
            print(f"Added note: {highlight['book_title']} - {highlight['chapter']}")
        except Exception as e:
            print(f"Error adding to Notion: {str(e)}")

def main():
    print("Starting WeRead to Notion sync...")
    highlights = get_weread_highlights()
    if highlights:
        sync_to_notion(highlights)
    print(f"Sync completed. Processed {len(highlights)} notes")

if __name__ == "__main__":
    main()
