import os
import json
import requests
import re
from google import genai
from src.core.config import Config

class PropGuardian:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def _fetch_single_page(self, url: str) -> dict:
        """Helper to fetch one page and extract text + links"""
        try:
            print(f"Crawling: {url}...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
            }
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            
            html = res.text
            
            # Simple Link Extraction (Regex for speed/independence)
            # Look for <a href="..."> that might be relevant
            links = re.findall(r'<a[^>]+href=["\'](.*?)["\']', html, flags=re.IGNORECASE)
            
            # Cleaning Text
            clean = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL)
            clean = re.sub(r'<style.*?>.*?</style>', '', clean, flags=re.DOTALL)
            clean = re.sub(r'<!--.*?-->', '', clean, flags=re.DOTALL)
            
            text_content = []
            for tag in ['p', 'h1', 'h2', 'h3', 'li', 'div', 'span']:
                matches = re.findall(f'<{tag}[^>]*>(.*?)</{tag}>', clean, flags=re.DOTALL)
                text_content.extend(matches)
            
            raw_text = " ".join(text_content)
            clean_text = re.sub(r'<[^>]+>', ' ', raw_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            return {"url": url, "text": clean_text, "links": links}
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return {"url": url, "text": "", "links": []}

    def fetch_rules_content(self, start_url: str) -> str:
        """
        Smart Spider: Fetches the URL + crawls relevant sub-links.
        """
        from urllib.parse import urljoin, urlparse

        # 1. Fetch Seed Page
        seed_data = self._fetch_single_page(start_url)
        full_content = f"--- SOURCE: {start_url} (MAIN PAGE) ---\n{seed_data['text'][:15000]}\n\n"
        
        # 2. Identify Relevant Sub-Links
        parsed_start = urlparse(start_url)
        base_domain = parsed_start.netloc
        # Allow subdomains (e.g. help.firm.com if start is firm.com)
        # Handle "www." prefix strip for comparison
        root_domain = base_domain.replace("www.", "")
        
        keywords = ["rule", "faq", "terms", "condition", "objectiv", "prohibit", "restrict", "scaling", "general", "drawdown", "instrument", "spec", "help", "support"]
        
        candidates = []
        seen_links = {start_url}
        
        for link in seed_data['links']:
            # Normalize Link
            full_link = urljoin(start_url, link)
            link_parsed = urlparse(full_link)
            link_domain = link_parsed.netloc.replace("www.", "")
            
            # Filter: Must share root domain (allow subdomains)
            if (link_domain == root_domain or link_domain.endswith("." + root_domain)) and full_link not in seen_links:
                if any(k in full_link.lower() for k in keywords):
                    candidates.append(full_link)
                    seen_links.add(full_link)

        # Prioritize most relevant links (heuristic: contains 'terms' or 'rules' is high value)
        # Limit to top 3 sub-pages to save time/bandwidth
        priority_links = sorted(list(set(candidates)), key=lambda l: 0 if 'rules' in l else 1)[:3]
        
        # 3. Fetch Sub-Pages
        for sub_url in priority_links:
            data = self._fetch_single_page(sub_url)
            if len(data['text']) > 500: # Only add if meaningful content
                full_content += f"--- SOURCE: {sub_url} (SUB-PAGE) ---\n{data['text'][:10000]}\n\n"
        
        return full_content

    def analyze_rules(self, text_or_url: str):
        """
        Analyzes prop firm rule text OR URL for adversarial design patterns.
        """
        content = text_or_url
        if text_or_url.startswith("http"):
            content = self.fetch_rules_content(text_or_url)
            
        if not self.client:
            return {
                "score": 0,
                "traps": [{"title": "API Key Missing", "detail": "Cannot analyze without Gemini API Key."}],
                "verdict": "Unknown"
            }

        prompt = f"""
        You are a Senior Trading Systems Engineer and Consumer Advocate. 
        Your job is to protect a trader from "Adversarial Design" in Prop Firm Rules.
        
        Analyze the following text (Prop Firm Rules/FAQ source) and identify "Traps":
        1. **Lot Size/Contract Tricks:** (e.g. 1 Lot != 1 Unit, Micro-lots).
        2. **Fee/Commission Drag:** High fees that eat expectancy.
        3. **Drawdown Mechanics:** Equity-based vs Balance-based trailing (Adversarial).
        4. **Restriction Traps:** News trading bans, consistency rules, IP flagging.

        INPUT TEXT:
        {content[:15000]}

        Output valid JSON only:
        {{
            "risk_score": (1-10, 10=Highly Predatory),
            "firm_name": "Inferred Name",
            "traps": [
                {{
                    "category": "Structure" | "Fees" | "Rules" | "Tech",
                    "severity": "High" | "Medium" | "Low",
                    "title": "Short Warning Title",
                    "description": "Detailed explanation of the trap and how to avoid it."
                }}
            ],
            "verdict": "Summary of the firm's alignment with professional trading.",
            "recommendation": "Actionable advice (e.g., 'Use Risk Calculator', 'Avoid News')."
        }}
        """

        # Try multiple models in case of 404/Deprecation
        models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
        
        last_error = None
        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
                return json.loads(response.text)
            except Exception as e:
                last_error = e
                # If 404, continue to next model. If other error (Auth), simple fail.
                if "404" not in str(e) and "NOT_FOUND" not in str(e):
                    break # Don't retry auth errors
        
        # If loop finishes without return
        import traceback
        return {
            "risk_score": 0,
            "firm_name": "Error",
            "traps": [{
                "category": "System",
                "severity": "High",
                "title": "Analysis Failed",
                "description": f"All models failed. Last Error: {str(last_error)}"
            }],
            "verdict": "System Error",
            "recommendation": "Check API Key or try pasting text manually."
        }
