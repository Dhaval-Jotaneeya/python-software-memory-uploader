import requests
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from config import Config

logger = logging.getLogger(__name__)

class GitHubService:
    """Service class for GitHub API operations"""
    
    def __init__(self):
        self.base_url = Config.GITHUB_API_BASE
        self.org = Config.GITHUB_ORG
        self.headers = {
            'Authorization': f"token {Config.GITHUB_TOKEN}",
            'Accept': 'application/vnd.github.v3+json'
        }
        self._rate_limit_remaining = None
        self._rate_limit_reset = None
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a GitHub API request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            self._check_rate_limit(response)
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            raise
    
    def _check_rate_limit(self, response: requests.Response) -> None:
        """Check and update rate limit information"""
        try:
            self._rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            self._rate_limit_reset = datetime.fromtimestamp(reset_time)
            
            if self._rate_limit_remaining < Config.RATE_LIMIT_CRITICAL_THRESHOLD:
                logger.warning(f"Critical rate limit: {self._rate_limit_remaining} remaining")
            elif self._rate_limit_remaining < Config.RATE_LIMIT_WARNING_THRESHOLD:
                logger.warning(f"Rate limit warning: {self._rate_limit_remaining} remaining")
                
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
    
    def get_rate_limit_info(self) -> Tuple[Optional[int], Optional[datetime]]:
        """Get current rate limit information"""
        return self._rate_limit_remaining, self._rate_limit_reset
    
    def get_repositories(self) -> List[Dict]:
        """Get all repositories for the organization"""
        response = self._make_request('GET', f'/orgs/{self.org}/repos')
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to fetch repositories: {response.status_code}")
    
    def create_repository(self, name: str, description: str = None) -> Dict:
        """Create a new repository"""
        data = {
            'name': name,
            'private': False,
            'description': description or 'Image repository created by Repository Manager',
            'has_issues': False,
            'has_projects': False,
            'has_wiki': False,
            'auto_init': True
        }
        
        response = self._make_request('POST', f'/orgs/{self.org}/repos', json=data)
        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Failed to create repository: {response.status_code}")
    
    def delete_repository(self, name: str) -> bool:
        """Delete a repository"""
        response = self._make_request('DELETE', f'/repos/{self.org}/{name}')
        return response.status_code == 204
    
    def get_repository_contents(self, repo_name: str, path: str = '') -> List[Dict]:
        """Get contents of a repository path"""
        response = self._make_request('GET', f'/repos/{self.org}/{repo_name}/contents/{path}')
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return []
        else:
            raise Exception(f"Failed to get repository contents: {response.status_code}")
    
    def upload_file(self, repo_name: str, path: str, content: str, message: str) -> Dict:
        """Upload a file to a repository"""
        data = {
            'message': message,
            'content': content
        }
        
        response = self._make_request('PUT', f'/repos/{self.org}/{repo_name}/contents/{path}', json=data)
        if response.status_code in [200, 201]:
            return response.json()
        else:
            raise Exception(f"Failed to upload file: {response.status_code}")
    
    def get_commits(self, repo_name: str, per_page: int = 100) -> List[Dict]:
        """Get commit history for a repository"""
        response = self._make_request('GET', f'/repos/{self.org}/{repo_name}/commits?per_page={per_page}')
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get commits: {response.status_code}")
    
    def enable_github_pages(self, repo_name: str, branch: str = 'gh-pages') -> Dict:
        """Enable GitHub Pages for a repository"""
        data = {
            'source': {
                'branch': branch,
                'path': '/'
            }
        }
        
        response = self._make_request('POST', f'/repos/{self.org}/{repo_name}/pages', json=data)
        if response.status_code in [200, 201]:
            return response.json()
        else:
            raise Exception(f"Failed to enable GitHub Pages: {response.status_code}")
    
    def get_github_pages_status(self, repo_name: str) -> Dict:
        """Get GitHub Pages status for a repository"""
        response = self._make_request('GET', f'/repos/{self.org}/{repo_name}/pages')
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {'status': 'not_enabled'}
        else:
            raise Exception(f"Failed to get GitHub Pages status: {response.status_code}")
    
    def create_blob(self, repo_name: str, content: str) -> str:
        """Create a blob and return its SHA"""
        data = {
            'content': content,
            'encoding': 'utf-8'
        }
        
        response = self._make_request('POST', f'/repos/{self.org}/{repo_name}/git/blobs', json=data)
        if response.status_code == 201:
            return response.json()['sha']
        else:
            raise Exception(f"Failed to create blob: {response.status_code}")
    
    def create_tree(self, repo_name: str, base_tree: str, tree_items: List[Dict]) -> str:
        """Create a tree and return its SHA"""
        data = {
            'base_tree': base_tree,
            'tree': tree_items
        }
        
        response = self._make_request('POST', f'/repos/{self.org}/{repo_name}/git/trees', json=data)
        if response.status_code == 201:
            return response.json()['sha']
        else:
            raise Exception(f"Failed to create tree: {response.status_code}")
    
    def create_commit(self, repo_name: str, message: str, tree_sha: str, parent_sha: str) -> str:
        """Create a commit and return its SHA"""
        data = {
            'message': message,
            'tree': tree_sha,
            'parents': [parent_sha]
        }
        
        response = self._make_request('POST', f'/repos/{self.org}/{repo_name}/git/commits', json=data)
        if response.status_code == 201:
            return response.json()['sha']
        else:
            raise Exception(f"Failed to create commit: {response.status_code}")
    
    def create_or_update_branch(self, repo_name: str, branch_name: str, commit_sha: str, force: bool = False) -> bool:
        """Create or update a branch reference"""
        data = {
            'sha': commit_sha,
            'force': force
        }
        
        # Try to update existing branch first
        response = self._make_request('PATCH', f'/repos/{self.org}/{repo_name}/git/refs/heads/{branch_name}', json=data)
        if response.status_code == 200:
            return True
        
        # If branch doesn't exist, create it
        if response.status_code == 422:  # Branch doesn't exist
            data = {
                'ref': f'refs/heads/{branch_name}',
                'sha': commit_sha
            }
            response = self._make_request('POST', f'/repos/{self.org}/{repo_name}/git/refs', json=data)
            return response.status_code == 201
        
        return False 