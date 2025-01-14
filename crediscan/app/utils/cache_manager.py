import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import HttpUrl

class CacheManager:
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.cache_dir = "cache"
        self.ensure_cache_dir()
        self.cache_path = os.path.join(self.cache_dir, cache_file)
        self.cache = self.load_cache()

    def ensure_cache_dir(self):
        """ensure cache directory exists"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def load_cache(self) -> Dict:
        """load cache file"""
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading cache {self.cache_file}: {e}")
            return {}

    def save_cache(self):
        """save cache to file"""
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving cache {self.cache_file}: {e}")

    def get_cache_key(self, params: Dict) -> str:
        """generate cache key"""
        # ensure all values are JSON serializable
        serializable_params = {}
        for k, v in params.items():
            if isinstance(v, list):
                # handle special types in list
                serializable_params[k] = [str(item) if isinstance(item, HttpUrl) else item for item in v]
            else:
                # handle other special types
                serializable_params[k] = str(v) if isinstance(v, HttpUrl) else v
        
        # convert params to sorted string
        sorted_params = sorted(serializable_params.items())
        return json.dumps(sorted_params, sort_keys=True)

    def get_cached_result(self, params: Dict) -> Optional[Dict]:
        """get cached result"""
        cache_key = self.get_cache_key(params)
        if cache_key in self.cache:
            print(f"Cache hit for {self.cache_file}")
            return self.cache[cache_key]
        print(f"Cache miss for {self.cache_file}")
        return None

    def save_result(self, params: Dict, result: Any):
        """save result to cache"""
        cache_key = self.get_cache_key(params)
        self.cache[cache_key] = {
            "params": params,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        self.save_cache() 