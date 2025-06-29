import time
import json
import logging
import hashlib
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from config import Config

logger = logging.getLogger(__name__)

class CacheItem:
    """Represents a cached item with expiration"""
    
    def __init__(self, data: Any, expiration_time: datetime):
        self.data = data
        self.expiration_time = expiration_time
        self.created_time = datetime.now()
    
    def is_expired(self) -> bool:
        """Check if the cache item has expired"""
        return datetime.now() > self.expiration_time
    
    def get_age(self) -> timedelta:
        """Get the age of the cache item"""
        return datetime.now() - self.created_time

class CacheManager:
    """Manages application caching"""
    
    def __init__(self):
        self._cache: Dict[str, CacheItem] = {}
        self._max_size = 1000  # Maximum number of cache items
        self._default_ttl = Config.CACHE_DURATION
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments"""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from cache"""
        if not Config.CACHE_ENABLED:
            return default
        
        if key in self._cache:
            item = self._cache[key]
            if item.is_expired():
                logger.debug(f"Cache item expired: {key}")
                del self._cache[key]
                return default
            else:
                logger.debug(f"Cache hit: {key}")
                return item.data
        else:
            logger.debug(f"Cache miss: {key}")
            return default
    
    def set(self, key: str, data: Any, ttl: int = None) -> None:
        """Set a value in cache"""
        if not Config.CACHE_ENABLED:
            return
        
        if ttl is None:
            ttl = self._default_ttl
        
        expiration_time = datetime.now() + timedelta(seconds=ttl)
        self._cache[key] = CacheItem(data, expiration_time)
        
        # Clean up if cache is too large
        if len(self._cache) > self._max_size:
            self._cleanup()
        
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
    
    def delete(self, key: str) -> bool:
        """Delete a value from cache"""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache deleted: {key}")
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache"""
        self._cache.clear()
        logger.debug("Cache cleared")
    
    def _cleanup(self) -> None:
        """Remove expired items and oldest items if cache is too large"""
        # Remove expired items
        expired_keys = [key for key, item in self._cache.items() if item.is_expired()]
        for key in expired_keys:
            del self._cache[key]
        
        # If still too large, remove oldest items
        if len(self._cache) > self._max_size:
            sorted_items = sorted(self._cache.items(), key=lambda x: x[1].created_time)
            items_to_remove = len(sorted_items) - self._max_size
            for i in range(items_to_remove):
                del self._cache[sorted_items[i][0]]
        
        logger.debug(f"Cache cleanup completed. Items: {len(self._cache)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_items = len(self._cache)
        expired_items = sum(1 for item in self._cache.values() if item.is_expired())
        valid_items = total_items - expired_items
        
        return {
            'total_items': total_items,
            'valid_items': valid_items,
            'expired_items': expired_items,
            'max_size': self._max_size,
            'cache_enabled': Config.CACHE_ENABLED
        }

class RepositoryCache:
    """Specialized cache for repository data"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.repo_list_key = "repo_list"
        self.repo_contents_key = "repo_contents"
        self.repo_commits_key = "repo_commits"
    
    def get_repositories(self) -> Optional[List[Dict]]:
        """Get cached repository list"""
        return self.cache_manager.get(self.repo_list_key)
    
    def set_repositories(self, repositories: List[Dict], ttl: int = 300) -> None:
        """Cache repository list"""
        self.cache_manager.set(self.repo_list_key, repositories, ttl)
    
    def get_repository_contents(self, repo_name: str, path: str = "") -> Optional[List[Dict]]:
        """Get cached repository contents"""
        key = f"{self.repo_contents_key}:{repo_name}:{path}"
        return self.cache_manager.get(key)
    
    def set_repository_contents(self, repo_name: str, path: str, contents: List[Dict], ttl: int = 180) -> None:
        """Cache repository contents"""
        key = f"{self.repo_contents_key}:{repo_name}:{path}"
        self.cache_manager.set(key, contents, ttl)
    
    def get_repository_commits(self, repo_name: str) -> Optional[List[Dict]]:
        """Get cached repository commits"""
        key = f"{self.repo_commits_key}:{repo_name}"
        return self.cache_manager.get(key)
    
    def set_repository_commits(self, repo_name: str, commits: List[Dict], ttl: int = 300) -> None:
        """Cache repository commits"""
        key = f"{self.repo_commits_key}:{repo_name}"
        self.cache_manager.set(key, commits, ttl)
    
    def invalidate_repository(self, repo_name: str) -> None:
        """Invalidate all cache entries for a repository"""
        # Remove repository contents cache
        contents_pattern = f"{self.repo_contents_key}:{repo_name}:"
        keys_to_remove = [key for key in self.cache_manager._cache.keys() if key.startswith(contents_pattern)]
        for key in keys_to_remove:
            self.cache_manager.delete(key)
        
        # Remove repository commits cache
        commits_key = f"{self.repo_commits_key}:{repo_name}"
        self.cache_manager.delete(commits_key)
        
        logger.debug(f"Invalidated cache for repository: {repo_name}")
    
    def invalidate_all(self) -> None:
        """Invalidate all repository cache"""
        # Remove all repository-related cache entries
        keys_to_remove = []
        for key in self.cache_manager._cache.keys():
            if (key.startswith(self.repo_contents_key) or 
                key.startswith(self.repo_commits_key) or 
                key == self.repo_list_key):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            self.cache_manager.delete(key)
        
        logger.debug("Invalidated all repository cache")

class ImageCache:
    """Specialized cache for image data"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.image_metadata_key = "image_metadata"
        self.image_pairs_key = "image_pairs"
    
    def get_image_metadata(self, repo_name: str) -> Optional[List[Dict]]:
        """Get cached image metadata"""
        key = f"{self.image_metadata_key}:{repo_name}"
        return self.cache_manager.get(key)
    
    def set_image_metadata(self, repo_name: str, metadata: List[Dict], ttl: int = 600) -> None:
        """Cache image metadata"""
        key = f"{self.image_metadata_key}:{repo_name}"
        self.cache_manager.set(key, metadata, ttl)
    
    def get_image_pairs(self, repo_name: str) -> Optional[List[tuple]]:
        """Get cached image pairs (thumbnail_url, original_url)"""
        key = f"{self.image_pairs_key}:{repo_name}"
        return self.cache_manager.get(key)
    
    def set_image_pairs(self, repo_name: str, image_pairs: List[tuple], ttl: int = 600) -> None:
        """Cache image pairs"""
        key = f"{self.image_pairs_key}:{repo_name}"
        self.cache_manager.set(key, image_pairs, ttl)
    
    def invalidate_repository_images(self, repo_name: str) -> None:
        """Invalidate image cache for a repository"""
        metadata_key = f"{self.image_metadata_key}:{repo_name}"
        pairs_key = f"{self.image_pairs_key}:{repo_name}"
        
        self.cache_manager.delete(metadata_key)
        self.cache_manager.delete(pairs_key)
        
        logger.debug(f"Invalidated image cache for repository: {repo_name}")

# Global cache instance
cache_manager = CacheManager()
repository_cache = RepositoryCache(cache_manager)
image_cache = ImageCache(cache_manager) 