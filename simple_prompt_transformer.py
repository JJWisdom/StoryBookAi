"""
simple_prompt_transformer.py - Complete and robust prompt transformer
"""

import re
import random
from typing import List, Dict, Set
import json
from pathlib import Path

class SimplePromptTransformer:
    """Enhanced sentence to Stable Diffusion prompt converter"""
    
    def __init__(self, config_path: str = None):
        # Load configuration if provided
        self.config = self._load_config(config_path)
        
        # Storybook-specific enhancements
        self.storybook_styles = [
            "children's book illustration",
            "whimsical illustration",
            "storybook art style",
            "colorful cartoon illustration",
            "fantasy art",
            "fairytale illustration",
            "animated movie style",
            "picture book illustration"
        ]
        
        # Quality boosters
        self.quality_tags = [
            "masterpiece",
            "best quality",
            "detailed",
            "high resolution",
            "sharp focus",
            "professional illustration",
            "beautiful composition"
        ]
        
        # Negative prompt template
        self.negative_prompt = (
            "blurry, bad quality, deformed, ugly, disfigured, poorly drawn, "
            "extra limbs, mutation, mutated, out of frame, watermark, signature, "
            "text, logo, worst quality, jpeg artifacts, poorly drawn face, "
            "bad anatomy, cloned face, gross proportions"
        )
        
        # Verb conjugation helper
        self.verb_suffixes = {
            'ing': ['ing', 'eing', 'ying'],
            'ed': ['ed', 'ied', 'ded'],
            's': ['s', 'es', 'ies']
        }
        
        # Common synonyms for enhancement
        self.synonyms = {
            "big": ["large", "huge", "enormous", "giant"],
            "small": ["tiny", "little", "miniature", "petite"],
            "happy": ["joyful", "cheerful", "delighted", "merry"],
            "sad": ["unhappy", "sorrowful", "melancholy", "gloomy"],
            "fast": ["quick", "rapid", "swift", "speedy"],
            "slow": ["sluggish", "leisurely", "gradual", "unhurried"],
            "beautiful": ["gorgeous", "stunning", "lovely", "exquisite"],
            "good": ["excellent", "great", "superb", "wonderful"]
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """Load transformer configuration"""
        default_config = {
            "max_prompt_length": 350,
            "min_keywords": 3,
            "style_variation": 0.3,  # 30% chance to vary style
            "synonym_chance": 0.25   # 25% chance to add synonym
        }
        
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except:
                pass
        
        return default_config
    
    def clean_and_tokenize(self, text: str) -> List[str]:
        """Clean text and tokenize into words"""
        if not text:
            return []
        
        # Lowercase and clean
        text = text.lower().strip()
        
        # Remove extra punctuation but keep important ones
        text = re.sub(r'[^\w\s.,!?\-]', ' ', text)
        
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Split into words
        words = text.split()
        
        return words
    
    def is_stop_word(self, word: str) -> bool:
        """Check if word is a stop word"""
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "as", "is", "was", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did",
            "from", "this", "that", "these", "those", "it", "its", "it's",
            "am", "are", "will", "would", "could", "should", "might",
            "very", "really", "quite", "just", "only", "also", "too"
        }
        
        return word in stop_words or len(word) < 3
    
    def conjugate_verb(self, word: str) -> str:
        """Try to conjugate verb to present participle"""
        # Common irregular verbs
        irregulars = {
            "run": "running", "ran": "running",
            "swim": "swimming", "swam": "swimming",
            "fly": "flying", "flew": "flying",
            "go": "going", "went": "going",
            "see": "seeing", "saw": "seeing",
            "take": "taking", "took": "taking",
            "make": "making", "made": "making",
            "come": "coming", "came": "coming",
            "know": "knowing", "knew": "knowing",
            "get": "getting", "got": "getting"
        }
        
        if word in irregulars:
            return irregulars[word]
        
        # Try regular conjugation
        if word.endswith('e'):
            return word[:-1] + 'ing'
        elif len(word) >= 3 and word[-1] not in 'aeiou' and word[-2] in 'aeiou':
            return word + word[-1] + 'ing'
        else:
            return word + 'ing'
    
    def enhance_keyword(self, word: str) -> List[str]:
        """Enhance a single keyword with synonyms and variations"""
        enhanced = [word]
        
        # Add synonym with probability
        if word in self.synonyms and random.random() < self.config["synonym_chance"]:
            synonym = random.choice(self.synonyms[word])
            enhanced.append(synonym)
        
        # Try to conjugate if it looks like a verb
        if len(word) >= 4 and not word.endswith(('ing', 'ed', 's')):
            conjugated = self.conjugate_verb(word)
            if conjugated != word:
                enhanced.append(conjugated)
        
        return enhanced
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract and enhance keywords from text"""
        words = self.clean_and_tokenize(text)
        
        keywords = []
        for word in words:
            # Clean the word
            word = word.strip('.,!?')
            
            # Skip stop words and short words
            if self.is_stop_word(word):
                continue
            
            # Enhance the word
            enhanced = self.enhance_keyword(word)
            keywords.extend(enhanced)
        
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for word in keywords:
            if word not in seen:
                seen.add(word)
                unique.append(word)
        
        return unique
    
    def build_prompt(self, keywords: List[str], style: str = None) -> str:
        """Build complete prompt from keywords"""
        if not keywords:
            return ""
        
        # Select style
        if not style:
            style = random.choice(self.storybook_styles)
        
        # Select quality tags (2-3 of them)
        num_quality = random.randint(2, 3)
        selected_quality = random.sample(self.quality_tags, min(num_quality, len(self.quality_tags)))
        
        # Build prompt parts
        parts = []
        
        # Add keywords
        parts.extend(keywords)
        
        # Add style
        parts.append(style)
        
        # Add quality tags
        parts.extend(selected_quality)
        
        # Join with commas
        prompt = ", ".join(parts)
        
        # Limit length
        max_len = self.config["max_prompt_length"]
        if len(prompt) > max_len:
            # Try to truncate at a comma
            truncated = prompt[:max_len]
            last_comma = truncated.rfind(',')
            if last_comma > max_len * 0.7:  # Keep most of it
                prompt = truncated[:last_comma]
            else:
                prompt = truncated
        
        return prompt
    
    def enhance_for_storybook(self, text: str) -> str:
        """
        Main method: Convert natural language to enhanced Stable Diffusion prompt
        for storybook illustrations
        """
        # Extract and enhance keywords
        keywords = self.extract_keywords(text)
        
        # Ensure minimum keywords
        if len(keywords) < self.config["min_keywords"]:
            # Fallback: use cleaned text as keywords
            words = self.clean_and_tokenize(text)
            keywords = [w for w in words if not self.is_stop_word(w)][:10]
        
        # Build prompt
        prompt = self.build_prompt(keywords)
        
        return prompt
    
    def get_negative_prompt(self) -> str:
        """Get negative prompt for image generation"""
        return self.negative_prompt
    
    def batch_enhance(self, texts: List[str]) -> List[str]:
        """Enhance multiple texts at once"""
        return [self.enhance_for_storybook(text) for text in texts]


# Singleton instance
_transformer_instance = None

def get_transformer(config_path: str = None) -> SimplePromptTransformer:
    """Get transformer instance (singleton)"""
    global _transformer_instance
    if _transformer_instance is None:
        _transformer_instance = SimplePromptTransformer(config_path)
    return _transformer_instance


# Test function
if __name__ == "__main__":
    transformer = SimplePromptTransformer()
    
    test_cases = [
        "The quick brown fox jumps over the lazy dog",
        "A beautiful princess in a magical castle with a friendly dragon",
        "Three little pigs building houses of straw, sticks, and bricks",
        "An astronaut discovering alien life on a distant planet",
        "Children flying colorful kites in a sunny park on a spring day"
    ]
    
    print("=" * 70)
    print("PROMPT TRANSFORMER TEST")
    print("=" * 70)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}:")
        print(f"  Original: {test}")
        
        keywords = transformer.extract_keywords(test)
        print(f"  Keywords: {', '.join(keywords[:8])}...")
        
        enhanced = transformer.enhance_for_storybook(test)
        print(f"  Enhanced: {enhanced}")
        
        print(f"  Length: {len(enhanced)} characters")
        print("-" * 70)