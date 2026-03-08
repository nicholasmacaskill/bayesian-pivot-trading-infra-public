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
            res = requests.get(url, headers=headers, timeout=15) # Increased timeout
            res.raise_for_status()
            
            html = res.text
            
            # Extract links specifically from <a> and buttons that might have href/onclick
            links = re.findall(r'href=["\'](.*?)["\']', html, flags=re.IGNORECASE)
            
            # Aggressive Text Cleaning for LLM tokens
            clean = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL)
            clean = re.sub(r'<style.*?>.*?</style>', '', clean, flags=re.DOTALL)
            clean = re.sub(r'<header.*?>.*?</header>', '', clean, flags=re.DOTALL)
            clean = re.sub(r'<footer.*?>.*?</footer>', '', clean, flags=re.DOTALL)
            clean = re.sub(r'<nav.*?>.*?</nav>', '', clean, flags=re.DOTALL)
            clean = re.sub(r'<!--.*?-->', '', clean, flags=re.DOTALL)
            
            # Extract text from semantic tags
            text_content = []
            for tag in ['p', 'h1', 'h2', 'h3', 'li', 'article', 'section']:
                matches = re.findall(f'<{tag}[^>]*>(.*?)</{tag}>', clean, flags=re.DOTALL)
                for m in matches:
                    mtext = re.sub(r'<[^>]+>', ' ', m)
                    text_content.append(mtext)
            
            raw_text = " ".join(text_content)
            clean_text = re.sub(r'\s+', ' ', raw_text).strip()
            
            return {"url": url, "text": clean_text, "links": links}
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return {"url": url, "text": "", "links": []}

    def fetch_rules_content(self, start_url: str) -> str:
        """
        Deep Spider: Fetches the URL + crawls critical FAQ/Legal/Rules links.
        """
        from urllib.parse import urljoin, urlparse

        # 1. Fetch Seed Page
        seed_data = self._fetch_single_page(start_url)
        full_content = f"--- SOURCE: {start_url} (ENTRY POINT) ---\n{seed_data['text'][:20000]}\n\n"
        
        # 2. Extract and Filter Relevant Sub-Links
        parsed_start = urlparse(start_url)
        base_domain = parsed_start.netloc
        root_domain = base_domain.replace("www.", "")
        
        # High-Value Keywords for Rule Detection
        keywords = [
            "rule", "faq", "terms", "condition", "objectiv", "prohibit", 
            "restrict", "scaling", "drawdown", "consistency", "news", 
            "payout", "leverage", "contract", "instrument", "legal"
        ]
        
        candidates = []
        seen_links = {start_url}
        
        for link in seed_data['links']:
            # Normalize Link
            try:
                full_link = urljoin(start_url, link)
                link_parsed = urlparse(full_link)
                link_domain = link_parsed.netloc.replace("www.", "")
                
                # Stay within root domain or trusted subdomains
                if (link_domain == root_domain or link_domain.endswith("." + root_domain)) and full_link not in seen_links:
                    if any(k in full_link.lower() for k in keywords):
                        candidates.append(full_link)
                        seen_links.add(full_link)
            except: continue

        # Prioritize and limit (Rules/Terms are highest priority)
        # Sort by relevance score
        def score_link(l):
            l_low = l.lower()
            if "rule" in l_low or "terms" in l_low: return 0
            if "faq" in l_low: return 1
            if "drawdown" in l_low: return 2
            return 3

        priority_links = sorted(list(set(candidates)), key=score_link)[:5] # Increased to 5 sub-pages
        
        # 3. Fetch Sub-Pages and aggregate
        for sub_url in priority_links:
            data = self._fetch_single_page(sub_url)
            if len(data['text']) > 300:
                full_content += f"--- SOURCE: {sub_url} (MANDATORY READING) ---\n{data['text'][:15000]}\n\n"
        
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
                "risk_score": 0,
                "traps": [{"title": "API Key Missing", "detail": "Cannot analyze without Gemini API Key."}],
                "verdict": "Unknown",
                "firm_name": "Unknown"
            }

        # Load Sovereign Prompts (Private IP)
        try:
            from src.sovereign_core.prompts.guardian_prompts import SOVEREIGN_GUARDIAN_PROMPT
            sovereign_prompt = SOVEREIGN_GUARDIAN_PROMPT
        except ImportError:
            sovereign_prompt = None

        if sovereign_prompt:
            prompt = sovereign_prompt.format(content=content[:40000])
        else:
            # Public Lite Version
            prompt = f"""
            Analyze the following prop firm rules for basic risks (drawdown, fees, execution).
            
            FIRM TEXT:
            {content[:10000]}
            
            Return JSON with risk_score (1-10) and traps list.
            """

        models_to_try = [
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-1.5-flash",
        ]
        
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
                if "404" not in str(e) and "NOT_FOUND" not in str(e):
                    break 
        
        return {
            "risk_score": 0,
            "firm_name": "Audit Error",
            "traps": [{
                "category": "System",
                "severity": "High",
                "title": "Audit Failed",
                "description": f"Auditor system failure: {str(last_error)}"
            }],
            "verdict": "Inconclusive",
            "recommendation": "Retry scan or check manual docs."
        }

    def batch_audit(self, override_firms=None):
        """Runs audit on all configured firms and returns results."""
        from src.core.config import Config
        from src.core.database import log_prop_audit
        
        firms = override_firms or Config.PROP_FIRMS
        results = []
        
        for key, info in firms.items():
            try:
                print(f"--- COMMENCING AUDIT: {info['name']} ---")
                audit = self.analyze_rules(info['url'])
                # Ensure firm_name is correct
                audit['firm_name'] = info['name']
                log_prop_audit(audit)
                results.append(audit)
            except Exception as e:
                print(f"Error auditing {info['name']}: {e}")
                
        return results
