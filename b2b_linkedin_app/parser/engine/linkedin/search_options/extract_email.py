# Enhanced extract_email.py
import requests
import logging
import re
import time
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class EmailExtractor:
    def __init__(self, hunter_api_key: str = None):
        self.hunter_api_key = hunter_api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def extract_personal_email(self, first_name: str, last_name: str, domain: str, company: str = None) -> Optional[str]:
        """
        Enhanced email extraction with multiple fallback methods
        """
        if not domain or not first_name or not last_name:
            return None
            
        # Clean domain
        clean_domain = self.clean_domain(domain)
        if not clean_domain:
            return None
            
        # Method 1: Hunter.io (if API key available)
        if self.hunter_api_key:
            email = self.try_hunter_api(first_name, last_name, clean_domain)
            if email:
                return email
                
        # Method 2: Common email pattern guessing
        email = self.guess_email_patterns(first_name, last_name, clean_domain)
        if email:
            return email
            
        # Method 3: Company-specific pattern detection
        if company:
            email = self.company_specific_patterns(first_name, last_name, clean_domain, company)
            if email:
                return email
                
        return None

    def try_hunter_api(self, first_name: str, last_name: str, domain: str) -> Optional[str]:
        """
        Try Hunter.io API with better error handling
        """
        try:
            url = (
                f"https://api.hunter.io/v2/email-finder"
                f"?domain={domain}&first_name={first_name}&last_name={last_name}"
                f"&api_key={self.hunter_api_key}"
            )
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                email_data = data.get("data", {})
                email = email_data.get("email")
                confidence = email_data.get("score", 0)
                
                if email and confidence > 30:  # Only accept if confidence > 30%
                    logger.info(f"[HUNTER] Found email {email} (score: {confidence})")
                    return email
                else:
                    logger.info(f"[HUNTER] Low confidence email for {first_name} {last_name} @ {domain}")
                    
            elif response.status_code == 429:
                logger.warning(f"[HUNTER] Rate limit reached")
            else:
                logger.warning(f"[HUNTER] API returned {response.status_code}")
                
        except Exception as e:
            logger.error(f"[HUNTER] Exception: {e}")
            
        return None

    def guess_email_patterns(self, first_name: str, last_name: str, domain: str) -> Optional[str]:
        """
        Guess email using common patterns
        """
        try:
            # Clean names
            first = self.clean_name(first_name)
            last = self.clean_name(last_name)
            
            if not first or not last:
                return None
                
            # Common email patterns (ordered by popularity)
            patterns = [
                f"{first}.{last}@{domain}",
                f"{first}@{domain}",
                f"{first}{last}@{domain}",
                f"{first[0]}{last}@{domain}",
                f"{first}.{last[0]}@{domain}",
                f"{first[0]}.{last}@{domain}",
                f"{last}.{first}@{domain}",
                f"{last}@{domain}",
            ]
            
            # For French companies, try common French patterns
            if domain.endswith('.fr'):
                patterns.extend([
                    f"{first}-{last}@{domain}",
                    f"{first}_{last}@{domain}",
                ])
            
            # Return most likely pattern (you could validate these with SMTP)
            for pattern in patterns:
                if self.is_valid_email_format(pattern):
                    logger.info(f"[PATTERN] Guessed email: {pattern}")
                    return pattern
                    
        except Exception as e:
            logger.warning(f"[PATTERN] Failed to guess patterns: {e}")
            
        return None

    def company_specific_patterns(self, first_name: str, last_name: str, domain: str, company: str) -> Optional[str]:
        """
        Company-specific email pattern detection
        """
        try:
            first = self.clean_name(first_name)
            last = self.clean_name(last_name)
            
            # Tech company patterns
            tech_keywords = ['saas', 'software', 'tech', 'ai', 'data', 'digital']
            if any(keyword in company.lower() for keyword in tech_keywords):
                tech_patterns = [
                    f"{first}@{domain}",
                    f"{first}.{last}@{domain}",
                    f"{first[0]}{last}@{domain}",
                ]
                for pattern in tech_patterns:
                    if self.is_valid_email_format(pattern):
                        logger.info(f"[TECH_PATTERN] Guessed tech company email: {pattern}")
                        return pattern
                        
            # Startup patterns (often use first name)
            startup_keywords = ['startup', 'founder', 'ceo']
            if any(keyword in company.lower() for keyword in startup_keywords):
                startup_patterns = [
                    f"{first}@{domain}",
                    f"ceo@{domain}",
                    f"founder@{domain}",
                ]
                for pattern in startup_patterns:
                    if self.is_valid_email_format(pattern):
                        logger.info(f"[STARTUP_PATTERN] Guessed startup email: {pattern}")
                        return pattern
                        
        except Exception as e:
            logger.warning(f"[COMPANY_PATTERN] Failed company-specific patterns: {e}")
            
        return None

    def clean_domain(self, domain: str) -> Optional[str]:
        """
        Clean and extract domain from URL
        """
        try:
            # Remove protocol
            domain = domain.replace('http://', '').replace('https://', '')
            # Remove www
            domain = domain.replace('www.', '')
            # Remove path
            domain = domain.split('/')[0]
            # Remove port
            domain = domain.split(':')[0]
            
            # Validate domain format
            if '.' in domain and len(domain) > 3:
                return domain.lower()
                
        except Exception as e:
            logger.warning(f"[CLEAN_DOMAIN] Failed to clean domain {domain}: {e}")
            
        return None

    def clean_name(self, name: str) -> str:
        """
        Clean name for email generation
        """
        # Remove accents and special characters
        name = re.sub(r'[àáâãäå]', 'a', name.lower())
        name = re.sub(r'[èéêë]', 'e', name)
        name = re.sub(r'[ìíîï]', 'i', name)
        name = re.sub(r'[òóôõö]', 'o', name)
        name = re.sub(r'[ùúûü]', 'u', name)
        name = re.sub(r'[ç]', 'c', name)
        name = re.sub(r'[ñ]', 'n', name)
        
        # Remove non-alphanumeric characters
        name = re.sub(r'[^a-z0-9]', '', name)
        
        return name

    def is_valid_email_format(self, email: str) -> bool:
        """
        Validate email format
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

# Updated function for use in your existing code
def extract_personal_email(first_name: str, last_name: str, domain: str, api_key: str = None, company: str = None) -> str | None:
    """
    Wrapper function to maintain compatibility with existing code
    """
    extractor = EmailExtractor(api_key)
    return extractor.extract_personal_email(first_name, last_name, domain, company)