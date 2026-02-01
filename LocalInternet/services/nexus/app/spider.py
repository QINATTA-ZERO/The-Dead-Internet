import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
from sqlalchemy import create_engine, text
import os
import urllib.parse

# Config
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/psx_core")
NEXUS_API = "http://localhost:80/api/index"
EXCLUDE_DOMAINS = [
    "compute.psx",
    "db.psx",
    "postgres.psx",
    "mcp.psx"
]

# Internal services that should be indexed but might not be in aether_domains
SEED_SERVICES = [
    "http://www.psx",
    "http://id.psx",
    "http://echo.psx",
    "http://bank.psx",
    "http://forge.psx",
    "http://mail.psx",
    "http://flux.psx",
    "http://aether.psx",
    "http://nexus.psx"
]

async def fetch(session, url):
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                return await response.text()
    except:
        pass
    return None

def get_registered_domains():
    engine = create_engine(DATABASE_URL)
    domains = []
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT domain_name FROM aether_domains"))
            for row in result:
                d = row[0]
                if d not in EXCLUDE_DOMAINS:
                    domains.append(f"http://{d}")
    except Exception as e:
        print(f"Error fetching domains from DB: {e}")
    return domains

async def index_url(session, url, html):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.string if soup.title else url
    
    # Extract text
    for script in soup(["script", "style"]):
        script.extract()
    text_content = soup.get_text()
    lines = (line.strip() for line in text_content.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    clean_text = '\n'.join(chunk for chunk in chunks if chunk)
    
    # Send to Index
    try:
        async with session.post(NEXUS_API, data={"url": url, "title": title, "content": clean_text}) as resp:
            if resp.status == 200:
                print(f"Indexed {url}")
            else:
                print(f"Failed to index {url}: {resp.status}")
    except Exception as e:
        print(f"Error calling index API for {url}: {e}")
    
    # Find links
    links = []
    for a in soup.find_all('a', href=True):
        link = a['href']
        full_url = urllib.parse.urljoin(url, link)
        # Only crawl internal .psx links
        if ".psx" in full_url and not any(ex in full_url for ex in EXCLUDE_DOMAINS):
            links.append(full_url)
    return links

async def crawl():
    print("Starting smart crawl...")
    
    all_seeds = list(set(SEED_SERVICES + get_registered_domains()))
    visited = set()
    queue = asyncio.Queue()
    
    for url in all_seeds:
        await queue.put(url)
        
    async with aiohttp.ClientSession() as session:
        while not queue.empty():
            url = await queue.get()
            if url in visited:
                queue.task_done()
                continue
            
            visited.add(url)
            print(f"Crawling {url}...")
            
            html = await fetch(session, url)
            if html:
                discovered_links = await index_url(session, url, html)
                # Limit depth/breadth for simple crawler
                for link in discovered_links:
                    if link not in visited:
                        await queue.put(link)
            
            queue.task_done()
            await asyncio.sleep(0.5) # Be polite to internal services

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(crawl())