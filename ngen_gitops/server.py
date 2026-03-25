#!/usr/bin/env python3
"""FastAPI web server for ngen-gitops."""
from __future__ import annotations

import sys
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from . import __version__
from .config import get_default_remote

from .bitbucket import GitOpsError as BitbucketError
from .github import GitOpsError as GithubError
GitOpsError = (BitbucketError, GithubError)

def get_provider():
    if 'github' in get_default_remote().lower():
        import ngen_gitops.github as provider
    else:
        import ngen_gitops.bitbucket as provider
    return provider

def create_branch(*args, **kwargs): return get_provider().create_branch(*args, **kwargs)
def set_image_in_yaml(*args, **kwargs): return get_provider().set_image_in_yaml(*args, **kwargs)
def create_pull_request(*args, **kwargs): return get_provider().create_pull_request(*args, **kwargs)
def merge_pull_request(*args, **kwargs): return get_provider().merge_pull_request(*args, **kwargs)
def run_k8s_pr_workflow(*args, **kwargs): return get_provider().run_k8s_pr_workflow(*args, **kwargs)


# Request models
class CreateBranchRequest(BaseModel):
    """Request model for create-branch endpoint."""
    repo: str
    src_branch: str
    dest_branch: str


class SetImageYamlRequest(BaseModel):
    """Request model for set-image-yaml endpoint."""
    repo: str
    refs: str
    yaml_path: str
    image: str
    dry_run: bool = False


class PullRequestRequest(BaseModel):
    """Request model for pull-request endpoint."""
    repo: str
    src_branch: str
    dest_branch: str
    delete_after_merge: bool = False


class MergeRequest(BaseModel):
    """Request model for merge endpoint."""
    pr_url: str
    delete_after_merge: bool = False


class K8sPRRequest(BaseModel):
    """Request model for k8s-pr endpoint."""
    cluster: str = Field(
        ...,
        description="Source branch in the GitOps repo (usually the cluster name, e.g. 'main' or 'k8s-cluster-1').",
        examples=["main"]
    )
    namespace: str = Field(
        ...,
        description="Kubernetes namespace. Used as a subfolder path in the GitOps repo.",
        examples=["my-ns"]
    )
    deploy: str = Field(
        ...,
        description="Deployment name. Used to locate the YAML file (e.g. '<namespace>/<deploy>_deployment.yaml').",
        examples=["my-app"]
    )
    image: str = Field(
        ...,
        description="Full container image string to deploy (e.g. 'myregistry/app:v2.1.0').",
        examples=["myregistry/app:v2.1.0"]
    )
    approve_merge: bool = Field(
        False,
        description="If true, automatically merge the PR after it is created. Default: false (PR is left open)."
    )
    repo: str = Field(
        "gitops-k8s",
        description="GitOps repository name. Overrides the K8S_PR_REPO config value. Default: 'gitops-k8s'.",
        examples=["gitops-k8s"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "cluster": "main",
                    "namespace": "my-ns",
                    "deploy": "my-app",
                    "image": "myregistry/app:v2.1.0",
                    "approve_merge": True,
                    "repo": "gitops-k8s"
                }
            ]
        }
    }


# Create FastAPI app
app = FastAPI(
    title="ngen-gitops API",
    description=(
        "GitOps REST API server for **GitHub** and **Bitbucket** operations.\n\n"
        "Automate Kubernetes deployment workflows including:\n"
        "- 🌿 Branch creation\n"
        "- 🖼️ Container image updates in YAML files\n"
        "- 🔄 Pull Request creation and merging\n"
        "- 🚀 Complete K8s GitOps workflow (`k8s-pr`)\n\n"
        "The active Git provider (GitHub or Bitbucket) is determined by `GIT_DEFAULT_REMOTE` in your config."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={"name": "ngen-gitops", "url": "https://github.com/mamatnurahmat/ngen-gitops"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return RedirectResponse(url="/docs")


@app.get("/api/sample", tags=["Sample"])
async def sample_api():
    """Sample API endpoint for testing Swagger documentation."""
    return {
        "message": "Welcome to ngen-gitops sample API!",
        "status": "success",
        "data": {
            "supported_providers": ["bitbucket", "github", "gitlab"],
            "features": ["branch_management", "kubernetes_gitops", "pull_requests"]
        }
    }


@app.get("/config", tags=["Config"])
async def get_config_info():
    """Get current system configuration (passwords and tokens masked)."""
    from .config import load_config
    config = load_config()
    
    # Mask sensitive information securely
    if "bitbucket" in config and "app_password" in config["bitbucket"]:
        if config["bitbucket"]["app_password"]:
            config["bitbucket"]["app_password"] = "***SET***"
            
    if "github" in config and "token" in config["github"]:
        if config["github"]["token"]:
            config["github"]["token"] = "***SET***"
            
    if "notifications" in config and "teams_webhook" in config["notifications"]:
        if config["notifications"]["teams_webhook"]:
            config["notifications"]["teams_webhook"] = "***SET***"
            
    return config


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


@app.post("/v1/gitops/create-branch")
async def api_create_branch(request: CreateBranchRequest):
    """Create a new branch in Bitbucket repository.
    
    Args:
        request: CreateBranchRequest with repo, src_branch, dest_branch
    
    Returns:
        JSON response with operation result
    
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = create_branch(
            repo=request.repo,
            src_branch=request.src_branch,
            dest_branch=request.dest_branch
        )
        
        if result['success']:
            return JSONResponse(content=result, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=result)
            
    except GitOpsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'GitOpsError'
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'ValueError'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }
        )


@app.post("/v1/gitops/set-image-yaml")
async def api_set_image_yaml(request: SetImageYamlRequest):
    """Update image reference in YAML file.
    
    Args:
        request: SetImageYamlRequest with repo, refs, yaml_path, image, dry_run
    
    Returns:
        JSON response with operation result
    
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = set_image_in_yaml(
            repo=request.repo,
            refs=request.refs,
            yaml_path=request.yaml_path,
            image=request.image,
            dry_run=request.dry_run
        )
        
        if result['success']:
            return JSONResponse(content=result, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=result)
            
    except GitOpsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'GitOpsError'
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'ValueError'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }
        )


@app.post("/v1/gitops/pull-request")
async def api_pull_request(request: PullRequestRequest):
    """Create a pull request in Bitbucket repository.
    
    Args:
        request: PullRequestRequest with repo, src_branch, dest_branch, delete_after_merge
    
    Returns:
        JSON response with operation result
    
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = create_pull_request(
            repo=request.repo,
            src_branch=request.src_branch,
            dest_branch=request.dest_branch,
            delete_after_merge=request.delete_after_merge
        )
        
        if result['success']:
            return JSONResponse(content=result, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=result)
            
    except GitOpsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'GitOpsError'
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'ValueError'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }
        )


@app.post("/v1/gitops/merge")
async def api_merge(request: MergeRequest):
    """Merge a pull request.
    
    Args:
        request: MergeRequest with pr_url, delete_after_merge
    
    Returns:
        JSON response with operation result
    
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = merge_pull_request(
            pr_url=request.pr_url,
            delete_after_merge=request.delete_after_merge
        )
        
        if result['success']:
            return JSONResponse(content=result, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=result)
            
    except GitOpsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'GitOpsError'
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'ValueError'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }
        )


@app.post(
    "/v1/gitops/k8s-pr",
    tags=["GitOps"],
    summary="Run Kubernetes PR Workflow",
    responses={
        200: {
            "description": "Workflow completed successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "merged": {
                            "summary": "PR created and merged",
                            "value": {
                                "success": True,
                                "steps": [
                                    {"name": "create_branch", "result": {"success": True, "branch_url": "https://github.com/org/gitops-k8s/tree/my-ns/my-app_deployment.yaml"}},
                                    {"name": "set_image",    "result": {"success": True, "commit": "[my-ns/my-app_deployment.yaml abc1234] chore: update image"}},
                                    {"name": "create_pr",   "result": {"success": True, "pr_id": 42, "pr_url": "https://github.com/org/gitops-k8s/pull/42"}},
                                    {"name": "merge_pr",    "result": {"success": True, "merge_commit": "abc1234"}}
                                ],
                                "pr_url": "https://github.com/org/gitops-k8s/pull/42",
                                "message": "Workflow completed successfully (merged)"
                            }
                        },
                        "pr_only": {
                            "summary": "PR created (not merged)",
                            "value": {
                                "success": True,
                                "steps": [
                                    {"name": "create_branch", "result": {"success": True}},
                                    {"name": "set_image",    "result": {"success": True}},
                                    {"name": "create_pr",   "result": {"success": True, "pr_url": "https://github.com/org/gitops-k8s/pull/42"}}
                                ],
                                "pr_url": "https://github.com/org/gitops-k8s/pull/42",
                                "message": "Workflow completed successfully (PR created)"
                            }
                        },
                        "skipped": {
                            "summary": "Image already up to date (skipped)",
                            "value": {
                                "success": True,
                                "steps": [
                                    {"name": "create_branch", "result": {"success": True}},
                                    {"name": "set_image",    "result": {"success": True, "skipped": True, "message": "Image already up-to-date: myregistry/app:v2.1.0"}}
                                ],
                                "pr_url": "",
                                "message": "Image already up to date"
                            }
                        }
                    }
                }
            }
        },
        400: {"description": "Workflow failed (bad request or GitOps error)"},
        500: {"description": "Internal server error"}
    }
)
async def api_k8s_pr(request: K8sPRRequest):
    """
    Run the full **Kubernetes GitOps PR Workflow**.

    Executes the following steps in sequence:

    1. **Create Branch** — creates `<namespace>/<deploy>_deployment.yaml` from `<cluster>`
       (branch name is configurable via `K8S_PR_BRANCH_TEMPLATE` in your `.env`).
    2. **Update Image** — clones the new branch and replaces the `image:` field
       in `<namespace>/<deploy>_deployment.yaml` with the new image tag
       (path configurable via `K8S_PR_YAML_TEMPLATE`).
    3. **Create PR** — opens a pull request from the new branch back to `<cluster>`.
    4. **Merge PR** *(optional)* — merges the PR immediately if `approve_merge` is `true`.

    > ⚠️ If the image in the YAML file is already set to the requested value,
    > the workflow stops after step 2 and returns `success: true` with `skipped: true`
    > on the `set_image` step — no PR is created.

    **Template defaults** (configurable in `~/.ngen-gitops/.env`):
    - `K8S_PR_BRANCH_TEMPLATE` = `{namespace}/{deploy}_deployment.yaml`
    - `K8S_PR_YAML_TEMPLATE`   = `{namespace}/{deploy}_deployment.yaml`
    - `K8S_PR_REPO`            = `gitops-k8s`
    """
    try:
        result = run_k8s_pr_workflow(
            cluster=request.cluster,
            namespace=request.namespace,
            deploy=request.deploy,
            image=request.image,
            approve_merge=request.approve_merge,
            repo=request.repo
        )
        
        if result.get('success', False):
            return JSONResponse(content=result, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=result)
            
    except GitOpsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'GitOpsError'
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'ValueError'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }
        )



def start_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the FastAPI server.
    
    Args:
        host: Server host address
        port: Server port number
    """
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    start_server()
