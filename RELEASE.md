# Release Notes — ngen-gitops\n
---\n
## v0.0.1.18 — 2026-03-25\n
### Changes\n
<!-- TODO: Add release notes for v0.0.1.18 above this line -->\n
---\n
## v0.1.17 — 2026-03-23\n
### Changes\n
<!-- TODO: Add release notes for v0.1.17 above this line -->\n

---

## v0.1.17 — 2026-03-23

### ✨ New Features

#### 🔀 REST API Server Improvements
- **Root redirect ke Swagger UI** — Mengakses `http://localhost:8080/` sekarang otomatis diarahkan ke halaman dokumentasi interaktif `/docs`, sehingga tidak perlu mengetik URL secara manual.
- **Endpoint `GET /config`** — Menampilkan konfigurasi aktif saat ini (provider, org, remote, server, registry). Nilai sensitif seperti token dan password otomatis disajikan sebagai `***SET***`.
- **Endpoint `GET /api/sample`** — Sample API endpoint sebagai demonstrasi di halaman Swagger UI.
- **Endpoint `POST /v1/gitops/k8s-pr`** — Endpoint API untuk menjalankan complete K8s GitOps workflow (Create Branch → Update Image → Create PR → Merge Opsional) sekarang tersedia via REST API, tidak hanya via CLI.

#### 🧩 Template Dinamis K8s-PR
Workflow `k8s-pr` kini mendukung **template yang dapat dikustomisasi** melalui file `.env`. Sebelumnya branch name dan YAML path di-hardcode sebagai `{namespace}/{deploy}_deployment.yaml`.

Tambahkan ke `~/.ngen-gitops/.env`:
```bash
# Template untuk nama branch yang dibuat
K8S_PR_BRANCH_TEMPLATE={namespace}/{deploy}_deployment.yaml

# Template untuk path file YAML yang diupdate
K8S_PR_YAML_TEMPLATE={namespace}/{deploy}_deployment.yaml

# Repository default untuk workflow k8s-pr
K8S_PR_REPO=gitops-k8s
```

**Placeholder tersedia:** `{cluster}`, `{namespace}`, `{deploy}`

**Contoh kustomisasi:**
```bash
# Struktur berbeda: cluster/namespace/deploy
K8S_PR_BRANCH_TEMPLATE={cluster}/{namespace}/{deploy}
K8S_PR_YAML_TEMPLATE=manifests/{namespace}/{deploy}_deploy.yaml
K8S_PR_REPO=my-gitops-repo
```

> ✅ Backward compatible — jika tidak dikonfigurasi, perilaku identik dengan versi sebelumnya.

#### 🛠️ Developer Experience
- **`make dev`** — Target baru di `Makefile` untuk menjalankan server FastAPI dalam mode development dengan hot-reload otomatis:
  ```bash
  make dev
  ```
  Ini memanggil `./venv/bin/uvicorn ngen_gitops.server:app --port 8080 --reload`.

- **Release Notes di `RELEASE.md`** — Makefile release sekarang secara otomatis membuat/mengupdate file `RELEASE.md` sebelum melakukan commit dan push.

### 📝 Documentation
- Ditambahkan **`PRD.md`** — Product Requirements Document yang mendeskripsikan fitur, target, NFR, dan roadmap project.
- Ditambahkan **`LOGS.md`** — Development Change Log yang mencatat setiap perubahan signifikan secara kronologis, dirancang agar mudah dipahami oleh LLM maupun developer baru.

### 🔧 Internal Changes
- `config.py`: Ditambahkan section `k8s_pr` di `load_config()` dan fungsi baru `get_k8s_pr_template()`.
- `bitbucket.py` & `github.py`: `run_k8s_pr_workflow()` direfaktor untuk membaca template dari config alih-alih hardcoded string.
- `server.py`: Import `RedirectResponse`, tambah 3 endpoint baru (`/`, `/config`, `/api/sample`, `/v1/gitops/k8s-pr`).

---

## v0.1.16 — 2026-03-17

- Penambahan Makefile dengan target: `all`, `venv`, `install`, `link`, `unlink`, `build`, `publish`, `release`, `clean`.
- Perbaikan alur instalasi dan symlink global.

---

## v0.1.15 — Rilis Awal

- Implementasi awal CLI dan Web Server.
- Support provider: Bitbucket (default) dan GitHub.
- Fitur: `create-branch`, `set-image-yaml`, `pull-request`, `merge`, `k8s-pr`, `clone`, `pull`, `push`, `fetch`, `commit`, `status`, `logs`, `get-file`, `tag`, `webhook`.
- FastAPI server dengan endpoint GitOps dasar.
- Notifikasi Microsoft Teams via webhook.
