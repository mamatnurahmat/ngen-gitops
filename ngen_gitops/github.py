"""GitHub API integration for GitOps operations."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
import yaml

from .config import get_github_credentials, get_k8s_pr_template
from .teams_notify import (
    notify_branch_created,
    notify_image_updated,
    notify_pr_created,
    notify_pr_merged
)

GITHUB_API_BASE = "https://api.github.com/repos"

class GitOpsError(Exception):
    """Base exception for GitOps operations."""
    pass


def list_pull_requests(
    repo: str,
    status: str = "open",
    token: Optional[str] = None,
    org: Optional[str] = None
) -> Dict[str, Any]:
    """List pull requests in a GitHub repository."""
    if not token or not org:
        creds = get_github_credentials()
        token = token or creds['token']
        org = org or creds['organization']
    
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    status_map = {
        'open': 'open',
        'merged': 'closed',
        'declined': 'closed',
        'draft': 'open'
    }
    
    api_state = status_map.get(status.lower(), 'open')
    
    result = {
        'success': False,
        'repository': repo,
        'status': status,
        'count': 0,
        'pull_requests': [],
        'message': ''
    }
    
    try:
        pr_url = f"{GITHUB_API_BASE}/{org}/{repo}/pulls?state={api_state}"
        resp = requests.get(pr_url, headers=headers, timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Repository '{repo}' not found")
        
        resp.raise_for_status()
        data = resp.json()
        
        prs = []
        for pr in data:
            # If asking for merged specifically, check merged_at
            if status.lower() == 'merged' and not pr.get('merged_at'):
                continue
            # If asking for declined (closed but not merged), check merged_at is null
            if status.lower() == 'declined' and pr.get('merged_at'):
                continue
            # If asking for draft, check draft flag
            if status.lower() == 'draft' and not pr.get('draft'):
                continue
                
            pr_data = {
                'id': pr.get('number'),
                'title': pr.get('title', ''),
                'source': pr.get('head', {}).get('ref', ''),
                'destination': pr.get('base', {}).get('ref', ''),
                'author': pr.get('user', {}).get('login', 'unknown'),
                'state': pr.get('state', ''),
                'created_on': pr.get('created_at', '')[:10] if pr.get('created_at') else '',
                'url': pr.get('html_url', '')
            }
            prs.append(pr_data)
        
        result['success'] = True
        result['count'] = len(prs)
        result['pull_requests'] = prs
        result['message'] = f"Found {len(prs)} pull request(s)"
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise

def get_pull_request_diff(
    repo: str,
    pr_id: int,
    token: Optional[str] = None,
    org: Optional[str] = None
) -> Dict[str, Any]:
    """Get diff for a specific pull request in GitHub."""
    if not token or not org:
        creds = get_github_credentials()
        token = token or creds['token']
        org = org or creds['organization']
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    
    result = {
        'success': False,
        'repository': repo,
        'pr_id': pr_id,
        'diff': '',
        'message': ''
    }
    
    try:
        diff_url = f"{GITHUB_API_BASE}/{org}/{repo}/pulls/{pr_id}"
        resp = requests.get(diff_url, headers=headers, timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Pull request #{pr_id} not found in repository '{repo}'")
        
        resp.raise_for_status()
        
        result['success'] = True
        result['diff'] = resp.text
        result['message'] = f"Retrieved diff for PR #{pr_id}"
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise

def create_branch(
    repo: str,
    src_branch: str,
    dest_branch: str,
    token: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new branch in GitHub repository from source branch."""
    if not token or not org:
        creds = get_github_credentials()
        token = token or creds['token']
        org = org or creds['organization']
        
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    result = {
        'success': False,
        'repository': repo,
        'source_branch': src_branch,
        'destination_branch': dest_branch,
        'message': ''
    }
    
    try:
        print(f"🔍 Creating branch '{dest_branch}' from '{src_branch}' in repository '{repo}'...")
        
        # Step 1: Validate source branch exists and get commit hash
        src_branch_url = f"{GITHUB_API_BASE}/{org}/{repo}/git/refs/heads/{src_branch}"
        resp = requests.get(src_branch_url, headers=headers, timeout=30)
        
        if resp.status_code == 404:
            raise GitOpsError(f"Source branch '{src_branch}' not found in repository '{repo}'")
        
        resp.raise_for_status()
        src_data = resp.json()
        
        commit_hash = src_data.get('object', {}).get('sha')
        if not commit_hash:
            raise GitOpsError(f"Could not get commit hash from source branch '{src_branch}'")
        
        print(f"✅ Source branch '{src_branch}' validated (commit: {commit_hash[:7]})")
        
        # Step 2: Create new branch
        create_url = f"{GITHUB_API_BASE}/{org}/{repo}/git/refs"
        payload = {
            "ref": f"refs/heads/{dest_branch}",
            "sha": commit_hash
        }
        
        create_resp = requests.post(create_url, headers=headers, json=payload, timeout=30)
        
        if create_resp.status_code == 422: # Reference already exists
            print(f"ℹ️  Branch '{dest_branch}' already exists")
            result['success'] = True
            result['message'] = f"Branch '{dest_branch}' already exists"
            result['branch_url'] = f"https://github.com/{org}/{repo}/tree/{dest_branch}"
            return result
        
        create_resp.raise_for_status()
        
        print(f"✅ Branch '{dest_branch}' created successfully from '{src_branch}'")
        result['success'] = True
        result['message'] = f"Branch '{dest_branch}' created successfully"
        result['branch_url'] = f"https://github.com/{org}/{repo}/tree/{dest_branch}"
        
        notify_branch_created(repo, src_branch, dest_branch, result['branch_url'], user=user)
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise GitOpsError(str(e)) from e


def _extract_yaml_image(data: Any) -> List[str]:
    images = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'image' and isinstance(value, str):
                images.append(value)
            else:
                images.extend(_extract_yaml_image(value))
    elif isinstance(data, list):
        for item in data:
            images.extend(_extract_yaml_image(item))
    return images

def _update_yaml_image(data: Any, new_image: str) -> bool:
    updated = False
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'image' and isinstance(value, str):
                data[key] = new_image
                updated = True
            else:
                updated = _update_yaml_image(value, new_image) or updated
    elif isinstance(data, list):
        for item in data:
            updated = _update_yaml_image(item, new_image) or updated
    return updated

def set_image_in_yaml(
    repo: str,
    refs: str,
    yaml_path: str,
    image: str,
    dry_run: bool = False,
    token: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Update image reference inside YAML file in GitHub repo."""
    if not token or not org:
        creds = get_github_credentials()
        token = token or creds['token']
        org = org or creds['organization']
        
    result = {
        'success': False,
        'repository': repo,
        'branch': refs,
        'yaml_path': yaml_path,
        'image': image,
        'message': ''
    }
    
    base_tmp = Path(tempfile.gettempdir()) / 'ngen-gitops-set-image-github'
    repo_dir = base_tmp / repo
    
    # Check if there is a known username for this token if needed or use 'gitops-bot'
    username = user or "gitops-bot"
    email = f"{username}@users.noreply.github.com"
    os.environ.setdefault('GIT_ASKPASS', 'true')
    
    clone_url = f"https://x-access-token:{quote(token, safe='')}@github.com/{org}/{repo}.git"
    
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        print(f"🔍 Cloning repository {repo} (branch: {refs})...")
        clone = subprocess.run(
            ['git', 'clone', '--single-branch', '--branch', refs, clone_url, str(repo_dir)],
            capture_output=True, text=True, check=False,
        )
        if clone.returncode != 0:
            raise GitOpsError(f"Git clone failed: {clone.stderr.strip()}")
        
        target_file = repo_dir / yaml_path
        if not target_file.exists():
            raise GitOpsError(f"File '{yaml_path}' not found in repository")
        
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise GitOpsError(f"Failed to parse YAML: {exc}")
        
        if data is None:
            raise GitOpsError("YAML file is empty or invalid")
            
        current_images = _extract_yaml_image(data)
        if current_images:
            print(f"   Current image(s): {', '.join(current_images)}")
            print(f"   New image: {image}")
            if image in current_images:
                result['success'] = True
                result['message'] = f"Image already up-to-date: {image}"
                result['skipped'] = True
                print(f"✅ Image already up-to-date")
                return result
                
        if not _update_yaml_image(data, image):
            raise GitOpsError(f"No 'image' field found to update in {yaml_path}")
            
        with open(target_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            
        print(f"✅ Updated image in YAML file")
        
        if dry_run:
            result['success'] = True
            result['message'] = 'Changes prepared (dry-run). No commit/push performed.'
            print("ℹ️  Dry-run mode: no commit/push")
            return result
            
        subprocess.run(['git', 'config', 'user.name', username], cwd=repo_dir, check=False)
        subprocess.run(['git', 'config', 'user.email', email], cwd=repo_dir, check=False)
        
        diff = subprocess.run(['git', 'status', '--porcelain'], cwd=repo_dir, capture_output=True, text=True)
        if not diff.stdout.strip():
            result['success'] = True
            result['message'] = 'No changes to commit'
            return result
            
        subprocess.run(['git', 'add', yaml_path], cwd=repo_dir, check=True)
        commit_msg = f"chore: update image to {image}"
        commit = subprocess.run(['git', 'commit', '-m', commit_msg], cwd=repo_dir, capture_output=True, text=True)
        if commit.returncode != 0:
            raise GitOpsError(f"Failed to commit changes: {commit.stderr.strip()}")
            
        push = subprocess.run(['git', 'push', 'origin', f"HEAD:{refs}"], cwd=repo_dir, capture_output=True, text=True)
        if push.returncode != 0:
            raise GitOpsError(f"Failed to push to origin: {push.stderr.strip()}")
            
        result['success'] = True
        result['message'] = f"Image updated to {image} and pushed to {refs}"
        result['commit'] = commit.stdout.strip()
        
        notify_image_updated(repo, refs, yaml_path, image, commit.stdout.strip(), user=user)
        return result
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Git operation failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise
    finally:
        if repo_dir.exists():
            shutil.rmtree(repo_dir)


def create_pull_request(
    repo: str,
    src_branch: str,
    dest_branch: str,
    delete_after_merge: bool = False,
    token: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Create a pull request in GitHub repository."""
    if not token or not org:
        creds = get_github_credentials()
        token = token or creds['token']
        org = org or creds['organization']
        
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    result = {
        'success': False,
        'repository': repo,
        'source': src_branch,
        'destination': dest_branch,
        'delete_after_merge': delete_after_merge,
        'pr_url': '',
        'message': ''
    }
    
    try:
        print(f"🔍 Creating pull request from '{src_branch}' to '{dest_branch}' in repository '{repo}'...")
        
        pr_url = f"{GITHUB_API_BASE}/{org}/{repo}/pulls"
        pr_payload = {
            "title": f"Merge {src_branch} into {dest_branch}",
            "body": "Auto-generated pull request from ngen-gitops",
            "head": src_branch,
            "base": dest_branch
        }
        
        pr_resp = requests.post(pr_url, headers=headers, json=pr_payload, timeout=30)
        
        if pr_resp.status_code == 422:
            error_data = pr_resp.json()
            errors = error_data.get('errors', [])
            error_msg = errors[0].get('message', 'Unknown error') if errors else 'Validation error'
            if 'A pull request already exists' in error_msg:
                # Find existing PR to return its URL
                check_pr_resp = requests.get(f"{pr_url}?head={org}:{src_branch}&base={dest_branch}", headers=headers)
                if check_pr_resp.status_code == 200 and check_pr_resp.json():
                    existing_pr = check_pr_resp.json()[0]
                    raise GitOpsError(f"Pull request already exists: {existing_pr.get('html_url')}")
            raise GitOpsError(f"Failed to create pull request: {error_msg}")
            
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()
        
        pr_id = pr_data.get('number')
        web_url = pr_data.get('html_url', '')
        
        print(f"✅ Pull request created successfully")
        print(f"   PR #{pr_id}")
        print(f"   URL: {web_url}")
        
        result['success'] = True
        result['pr_id'] = pr_id
        result['pr_url'] = web_url
        result['message'] = f"Pull request #{pr_id} created successfully"
        
        notify_pr_created(repo, src_branch, dest_branch, str(pr_id), web_url, user=user)
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise

def merge_pull_request(
    pr_url: str,
    delete_after_merge: bool = False,
    token: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Merge a pull request from GitHub PR URL."""
    if not token:
        creds = get_github_credentials()
        token = creds['token']
        
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    result = {
        'success': False,
        'pr_url': pr_url,
        'repository': '',
        'pr_id': '',
        'source': '',
        'destination': '',
        'message': '',
        'delete_after_merge': delete_after_merge
    }
    
    try:
        # Example URL: https://github.com/org/repo/pull/123
        url_pattern = r'https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)'
        match = re.search(url_pattern, pr_url)
        
        if not match:
            raise GitOpsError(f"Invalid pull request URL format. Expected: https://github.com/org/repo/pull/ID")
        
        org_from_url, repo, pr_id = match.groups()
        result['repository'] = repo
        result['pr_id'] = pr_id
        
        # Get PR details to find source branch to delete later if requested
        pr_details_url = f"{GITHUB_API_BASE}/{org_from_url}/{repo}/pulls/{pr_id}"
        resp = requests.get(pr_details_url, headers=headers, timeout=30)
        resp.raise_for_status()
        pr_data = resp.json()
        
        source_branch = pr_data.get('head', {}).get('ref', 'unknown')
        dest_branch = pr_data.get('base', {}).get('ref', 'unknown')
        result['source'] = source_branch
        result['destination'] = dest_branch
        
        if pr_data.get('merged'):
            print(f"✅ Pull request #{pr_id} is already merged")
            merge_hash = pr_data.get('merge_commit_sha', 'unknown')
            short_hash = merge_hash[:7] if len(merge_hash) >= 7 else merge_hash
            result['merge_commit'] = short_hash
            result['success'] = True
            result['message'] = 'Pull request already merged'
            return result
        
        if pr_data.get('state') == 'closed':
            raise GitOpsError(f"Pull request #{pr_id} is closed. Cannot merge.")
            
        merge_url = f"{GITHUB_API_BASE}/{org_from_url}/{repo}/pulls/{pr_id}/merge"
        merge_payload = {
            "commit_title": f"Merged pull request #{pr_id} via ngen-gitops",
            "merge_method": "merge"
        }
        
        merge_resp = requests.put(merge_url, headers=headers, json=merge_payload, timeout=30)
        
        if merge_resp.status_code in [405, 409]:
            raise GitOpsError(f"Pull request #{pr_id} cannot be merged automatically.")
            
        merge_resp.raise_for_status()
        merge_data = merge_resp.json()
        
        merge_commit = merge_data.get('sha', 'unknown')
        short_hash = merge_commit[:7] if len(merge_commit) >= 7 else merge_commit
        
        print(f"✅ Pull request #{pr_id} merged successfully")
        
        if delete_after_merge and source_branch != 'unknown':
            del_ref_url = f"{GITHUB_API_BASE}/{org_from_url}/{repo}/git/refs/heads/{source_branch}"
            del_resp = requests.delete(del_ref_url, headers=headers, timeout=30)
            if del_resp.status_code == 204:
                print(f"✅ Source branch '{source_branch}' deleted")
        
        result['success'] = True
        result['merge_commit'] = short_hash
        result['message'] = f"Pull request #{pr_id} merged successfully"
        
        notify_pr_merged(repo, str(pr_id), source_branch, dest_branch, short_hash, user=user)
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise

def run_k8s_pr_workflow(
    cluster: str,
    namespace: str,
    deploy: str,
    image: str,
    approve_merge: bool = False,
    repo: str = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Run complete K8s PR workflow for GitHub.

    Template placeholders: {cluster}, {namespace}, {deploy}
    Configure via .env:
      K8S_PR_BRANCH_TEMPLATE={namespace}/{deploy}_deployment.yaml
      K8S_PR_YAML_TEMPLATE={namespace}/{deploy}_deployment.yaml
      K8S_PR_REPO=gitops-k8s
    """
    tmpl = get_k8s_pr_template()
    ctx = {'cluster': cluster, 'namespace': namespace, 'deploy': deploy}
    dest_branch = tmpl['branch_template'].format(**ctx)
    yaml_path = tmpl['yaml_template'].format(**ctx)
    effective_repo = repo if repo is not None else tmpl['repo']
    
    print(f"🚀 Starting GitHub K8s PR Workflow for {deploy} in {namespace}")
    print(f"   Repo: {effective_repo}")
    print(f"   Cluster/Source: {cluster}")
    print(f"   Branch: {dest_branch}")
    print(f"   YAML path: {yaml_path}")
    print(f"   Image: {image}")
    
    workflow_result: Dict[str, Any] = {
        "success": False,
        "steps": [],
        "pr_url": "",
        "message": ""
    }
    
    try:
        # Step 1: Create Branch
        print("\n[Step 1/4] Creating branch...")
        branch_res = create_branch(repo=effective_repo, src_branch=cluster, dest_branch=dest_branch, user=user)
        workflow_result["steps"].append({"name": "create_branch", "result": branch_res})
        
        # Step 2: Set Image
        print("\n[Step 2/4] Updating image in YAML...")
        image_res = set_image_in_yaml(repo=effective_repo, refs=dest_branch, yaml_path=yaml_path, image=image, user=user)
        workflow_result["steps"].append({"name": "set_image", "result": image_res})
        
        if image_res.get('skipped'):
            print("⚠️  Image already up to date, stopping workflow.")
            workflow_result["success"] = True
            workflow_result["message"] = "Image already up to date"
            return workflow_result

        # Step 3: Create PR
        print("\n[Step 3/4] Creating Pull Request...")
        pr_res = create_pull_request(repo=effective_repo, src_branch=dest_branch, dest_branch=cluster, delete_after_merge=True, user=user)
        workflow_result["steps"].append({"name": "create_pr", "result": pr_res})
        workflow_result["pr_url"] = pr_res.get("pr_url")
        
        # Step 4: Merge (Optional)
        if approve_merge:
            print("\n[Step 4/4] Merging Pull Request...")
            merge_res = merge_pull_request(pr_url=pr_res["pr_url"], delete_after_merge=True, user=user)
            workflow_result["steps"].append({"name": "merge_pr", "result": merge_res})
            workflow_result["message"] = "Workflow completed successfully (merged)"
        else:
            print("\n[Step 4/4] Skipping merge (use --approve-merge to auto-merge)")
            workflow_result["message"] = "Workflow completed successfully (PR created)"
            
        workflow_result["success"] = True
        return workflow_result
        
    except Exception as e:
        print(f"\n❌ Workflow failed: {str(e)}")
        workflow_result["message"] = str(e)
        workflow_result["success"] = False
        return workflow_result

def create_tag(
    repo: str,
    branch: str,
    commit_id: str,
    tag_name: str,
    token: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Create a tag on a specific commit in GitHub repository."""
    if not token or not org:
        creds = get_github_credentials()
        token = token or creds['token']
        org = org or creds['organization']
        
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    result = {
        'success': False,
        'repository': repo,
        'branch': branch,
        'commit_id': commit_id,
        'tag_name': tag_name,
        'message': ''
    }
    
    try:
        # Step 1: validate branch/commit
        commit_url = f"{GITHUB_API_BASE}/{org}/{repo}/commits/{commit_id}"
        resp = requests.get(commit_url, headers=headers, timeout=30)
        if resp.status_code == 404:
            raise GitOpsError(f"Commit '{commit_id}' not found in repository '{repo}'")
        resp.raise_for_status()
        commit_data = resp.json()
        commit_hash = commit_data.get('sha', commit_id)
        
        # Step 2: create ref
        ref_url = f"{GITHUB_API_BASE}/{org}/{repo}/git/refs"
        payload = {
            "ref": f"refs/tags/{tag_name}",
            "sha": commit_hash
        }
        create_resp = requests.post(ref_url, headers=headers, json=payload, timeout=30)
        
        if create_resp.status_code == 422:
            print(f"ℹ️  Tag '{tag_name}' already exists")
            result['success'] = True
            result['message'] = f"Tag '{tag_name}' already exists"
            result['tag_url'] = f"https://github.com/{org}/{repo}/releases/tag/{tag_name}"
            return result
            
        create_resp.raise_for_status()
        
        result['success'] = True
        result['message'] = f"Tag {tag_name} created successfully"
        result['tag_url'] = f"https://github.com/{org}/{repo}/releases/tag/{tag_name}"
        result['commit_hash'] = commit_hash
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        result['message'] = error_msg
        raise GitOpsError(error_msg) from e
    except Exception as e:
        result['message'] = str(e)
        raise

def manage_webhook(
    repo: str,
    webhook_url: str,
    delete: bool = False,
    token: Optional[str] = None,
    org: Optional[str] = None,
    user: Optional[str] = None
) -> Dict[str, Any]:
    """Manage webhook in GitHub repository."""
    # Simplified stub for webhooks on Github. Usually need specific events mapping.
    if not token or not org:
        creds = get_github_credentials()
        token = token or creds['token']
        org = org or creds['organization']
        
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    result = {
        'success': False,
        'repository': repo,
        'webhook_url': webhook_url,
        'action': 'deleted' if delete else 'created',
        'message': ''
    }
    
    try:
        hooks_url = f"{GITHUB_API_BASE}/{org}/{repo}/hooks"
        resp = requests.get(hooks_url, headers=headers, timeout=30)
        resp.raise_for_status()
        hooks = resp.json()
        
        hook_id = None
        for hook in hooks:
            if hook.get('config', {}).get('url') == webhook_url:
                hook_id = hook.get('id')
                break
                
        if delete:
            if not hook_id:
                result['success'] = True
                result['message'] = "Webhook does not exist"
                return result
                
            del_url = f"{hooks_url}/{hook_id}"
            requests.delete(del_url, headers=headers, timeout=30).raise_for_status()
            result['success'] = True
            result['message'] = "Webhook deleted successfully"
            return result
            
        else:
            if hook_id:
                result['success'] = True
                result['message'] = "Webhook already exists"
                result['webhook_uuid'] = str(hook_id)
                return result
                
            payload = {
                "name": "web",
                "active": True,
                "events": ["push", "pull_request"],
                "config": {
                    "url": webhook_url,
                    "content_type": "json"
                }
            }
            create_resp = requests.post(hooks_url, headers=headers, json=payload, timeout=30)
            create_resp.raise_for_status()
            new_hook = create_resp.json()
            
            result['success'] = True
            result['message'] = "Webhook created successfully"
            result['webhook_uuid'] = str(new_hook.get('id'))
            result['events'] = new_hook.get('events', [])
            return result
            
    except Exception as e:
        result['message'] = str(e)
        raise GitOpsError(str(e)) from e
