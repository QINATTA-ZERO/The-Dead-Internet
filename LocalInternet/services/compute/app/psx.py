import requests
from bs4 import BeautifulSoup
import os
import time
import argparse
import sys
from urllib.parse import urljoin

# Detect Proxy from environment (default to 3128 if not set)
PROXY = os.getenv("http_proxy") or os.getenv("HTTP_PROXY") or "http://127.0.0.1:3128"

class Browser:
    def __init__(self):
        self.session = requests.Session()
        # Configure proxy for the session
        if PROXY:
            print(f"DEBUG: Using proxy {PROXY}", file=sys.stderr)
            self.session.proxies = {
                "http": PROXY,
                "https": PROXY
            }
        self.current_url = None
        self.soup = None

    def visit(self, url):
        """Navigates to the specified URL."""
        if not url.startswith("http"):
            url = "http://" + url.lstrip("/")
        
        try:
            resp = self.session.get(url)
            self._update_state(resp)
            return self.soup
        except Exception as e:
            print(f"[!] Error: {e}", file=sys.stderr)
            return None

    def post(self, url, data):
        if not url.startswith("http"):
            url = "http://" + url.lstrip("/")
        
        # Auto-correction for common agent mistakes
        if "echo.psx" in url and not url.endswith("/transmit"):
            url = "http://echo.psx/transmit"
        if "bank.psx" in url and not url.endswith("/transfer"):
            url = "http://bank.psx/transfer"
            
        try:
            resp = self.session.post(url, data=data)
            self._update_state(resp)
            return self.soup
        except Exception as e:
            print(f"[!] Error: {e}", file=sys.stderr)
            return None

    def _update_state(self, resp):
        self.current_url = resp.url
        self.soup = BeautifulSoup(resp.text, "html.parser")
    
    def get_text(self):
        if not self.soup: return ""
        # Remove script and style elements
        for script in self.soup(["script", "style"]):
            script.extract()
        text = self.soup.get_text()
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        return text

    def get_links(self):
        if not self.soup: return []
        links = []
        for a in self.soup.find_all('a', href=True):
            links.append({
                "text": a.get_text(strip=True) or "[IMG]",
                "href": urljoin(self.current_url, a['href'])
            })
        return links

    def get_forms(self):
        if not self.soup: return []
        forms = []
        for f in self.soup.find_all('form'):
            action = urljoin(self.current_url, f.get('action', ''))
            method = f.get('method', 'get').upper()
            inputs = []
            for i in f.find_all(['input', 'textarea', 'select']):
                name = i.get('name')
                if name:
                    inputs.append({
                        "name": name,
                        "type": i.get('type', 'text'),
                        "value": i.get('value', '')
                    })
            forms.append({"action": action, "method": method, "inputs": inputs})
        return forms

def main():
    parser = argparse.ArgumentParser(description="PSX Network Browser CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Read
    p_read = subparsers.add_parser("read", help="Fetch URL and print text content")
    p_read.add_argument("url", help="URL to visit")

    # Dump
    p_dump = subparsers.add_parser("dump", help="Fetch URL and print raw HTML")
    p_dump.add_argument("url", help="URL to visit")

    # Links
    p_links = subparsers.add_parser("links", help="List all links on page")
    p_links.add_argument("url", help="URL to visit")

    # Forms
    p_forms = subparsers.add_parser("forms", help="Analyze forms on page")
    p_forms.add_argument("url", help="URL to visit")

    # Post
    p_post = subparsers.add_parser("post", help="Submit POST data")
    p_post.add_argument("url", help="URL to submit to")
    p_post.add_argument("data", nargs="+", help="Data in key=value format")

    args = parser.parse_args()
    browser = Browser()

    if args.command == "read":
        browser.visit(args.url)
        print(f"--- CONTENT: {browser.current_url} ---")
        print(browser.get_text())
    
    elif args.command == "dump":
        browser.visit(args.url)
        if browser.soup:
            print(browser.soup.prettify())

    elif args.command == "links":
        browser.visit(args.url)
        print(f"--- LINKS: {browser.current_url} ---")
        for link in browser.get_links():
            print(f"[{link['text']}] -> {link['href']}")

    elif args.command == "forms":
        browser.visit(args.url)
        print(f"--- FORMS: {browser.current_url} ---")
        for i, f in enumerate(browser.get_forms()):
            print(f"FORM #{i+1}: {f['method']} {f['action']}")
            for inp in f['inputs']:
                print(f"  - {inp['name']} ({inp['type']}) default='{inp['value']}'")
    
    elif args.command == "post":
        data = {}
        for item in args.data:
            if "=" in item:
                k, v = item.split("=", 1)
                data[k] = v
        
        browser.post(args.url, data)
        print(f"--- RESPONSE: {browser.current_url} ---")
        print(browser.get_text())

if __name__ == "__main__":
    main()
