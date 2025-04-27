import requests
import json
import os
from datetime import datetime, timedelta
from notion_client import Client

# 配置信息
CONFIG = {
    "WEREAD_COOKIE": os.getenv("WEREAD_COOKIE"),  # 微信读书的cookie
    "NOTION_TOKEN": os.getenv("NOTION_TOKEN"),    # Notion集成token
    "NOTION_DATABASE_ID": os.getenv("NOTION_DATABASE_ID")  # Notion数据库ID
}

def get_weread_highlights():
    """获取微信读书的划线笔记"""
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
            
            # 获取每本书的详细笔记
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
        print(f"获取微信读书笔记失败: {str(e)}")
        return []

def sync_to_notion(highlights):
    """将笔记同步到Notion"""
    notion = Client(auth=CONFIG["NOTION_TOKEN"])
    
    for highlight in highlights:
        # 检查是否已存在相同的笔记
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
            print(f"笔记已存在: {highlight['book_title']} - {highlight['chapter']}")
            continue
        
        # 创建新笔记
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
            print(f"成功添加笔记: {highlight['book_title']} - {highlight['chapter']}")
        except Exception as e:
            print(f"添加笔记失败: {str(e)}")

def main():
    print("开始同步微信读书笔记到Notion...")
    highlights = get_weread_highlights()
    if highlights:
        sync_to_notion(highlights)
    print(f"同步完成，共处理{len(highlights)}条笔记")

if __name__ == "__main__":
    main()
GitHub Actions 配置
在项目根目录下创建 .github/workflows/sync_notes.yml 文件：

yaml
name: Sync WeRead to Notion

on:
  schedule:
    - cron: '0 19 * * *'  # 每天UTC时间19:00（北京时间第二天3:00）运行
  workflow_dispatch:  # 允许手动触发

jobs:
  sync:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.8'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests notion-client
    
    - name: Run sync script
      env:
        WEREAD_COOKIE: ${{ secrets.WEREAD_COOKIE }}
        NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
        NOTION_DATABASE_ID: ${{ secrets.NOTION_DATABASE_ID }}
      run: python sync_weread_to_notion.py
