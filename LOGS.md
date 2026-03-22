# LOGS.md — Development Change Log

> Dokumen ini mencatat semua perubahan signifikan pada project **ngen-gitops** secara kronologis.
> Format ini dirancang agar mudah dipahami oleh manusia maupun LLM (Large Language Model) di masa mendatang.
> Setiap entri menjelaskan **apa** yang berubah, **mengapa**, dan **implikasi** terhadap code base.

---

## Konvensi Format

```
## [YYYY-MM-DD] Judul Perubahan
- **Jenis:** Feature | Bugfix | Refactor | Docs | Config
- **File:** daftar file yang diubah
- **Ringkasan:** Penjelasan singkat
- **Detail:** Penjelasan teknis yang lebih dalam
- **Implikasi:** Apa yang harus diperhatikan oleh pengembang / LLM berikutnya
```

---

## [2026-03-23] Sesi Pengembangan: Docs, API Server, dan Template Dinamis K8s-PR

### 1. Pembuatan PRD (Product Requirements Document)
- **Jenis:** Docs
- **File:** `PRD.md` (baru), `LOGS.md` (baru)
- **Ringkasan:** Dibuat PRD dari *existing project* berdasarkan informasi di `PLAN.md` dan `README.md`.
- **Detail:** PRD mencakup Product Vision, Target Audience, Feature Requirements, NFR, dan Roadmap.
- **Implikasi:** PRD harus diupdate setiap kali ada perubahan signifikan pada fitur atau arsitektur.

---

### 2. Root Redirect ke Swagger UI
- **Jenis:** Feature
- **File:** `ngen_gitops/server.py`
- **Ringkasan:** Endpoint `GET /` yang sebelumnya mengembalikan JSON info endpoint, diubah menjadi redirect ke halaman Swagger UI `/docs`.
- **Detail:**
  - Import `RedirectResponse` ditambahkan dari `fastapi.responses`.
  - Handler `root()` sekarang menggunakan `RedirectResponse(url="/docs")`.
  - `include_in_schema=False` ditambahkan agar endpoint `/` tidak muncul di Swagger spec.
- **Implikasi:** Jika ada client yang secara programatis memanggil `GET /` dan mengharapkan JSON, perilaku ini sudah berubah (response 307 Redirect). Gunakan `/health` atau `/api/sample` untuk health probe.

---

### 3. Sample API Endpoint
- **Jenis:** Feature
- **File:** `ngen_gitops/server.py`
- **Ringkasan:** Ditambahkan endpoint `GET /api/sample` sebagai contoh API yang muncul di Swagger Docs.
- **Detail:** Response berisi `message`, `status`, dan `data` (supported_providers, features). Di-tag sebagai `"Sample"` di Swagger.
- **Implikasi:** Endpoint ini hanya untuk demonstrasi/testing, tidak melakukan operasi apapun ke Git.

---

### 4. Config API Endpoint
- **Jenis:** Feature
- **File:** `ngen_gitops/server.py`
- **Ringkasan:** Ditambahkan endpoint `GET /config` yang menampilkan konfigurasi sistem aktif dari `.env`.
- **Detail:**
  - Memanggil `load_config()` dari `config.py`.
  - Nilai sensitif (`github.token`, `bitbucket.app_password`, `notifications.teams_webhook`) dimasking menjadi `"***SET***"` jika sudah diisi, kosong jika belum diisi.
  - Di-tag sebagai `"Config"` di Swagger.
- **Implikasi:** Endpoint ini aman untuk development tetapi **jangan expose ke publik tanpa autentikasi** di production karena menampilkan metadata konfigurasi (org name, remote, registry, dll.).

---

### 5. Endpoint POST /v1/gitops/k8s-pr di Web Server
- **Jenis:** Feature
- **File:** `ngen_gitops/server.py`
- **Ringkasan:** Endpoint `POST /v1/gitops/k8s-pr` yang sebelumnya hanya ada di CLI, kini juga tersedia sebagai REST API endpoint di server.
- **Detail:**
  - Menggunakan model Pydantic `K8sPRRequest` (sudah ada sebelumnya).
  - Memanggil `run_k8s_pr_workflow()` dari provider yang aktif.
  - Di-tag sebagai `"GitOps"` di Swagger sehingga tampil bersama endpoint GitOps lainnya.
- **Implikasi:** Endpoint ini memicu operasi Git nyata (clone, commit, push, create PR) sehingga memerlukan kredensial yang valid di `.env` atau environment variables.

---

### 6. Target `make dev` di Makefile
- **Jenis:** Feature (DX)
- **File:** `Makefile`
- **Ringkasan:** Ditambahkan target `make dev` untuk menjalankan server FastAPI dalam mode development dengan hot-reload otomatis menggunakan uvicorn.
- **Detail:**
  ```makefile
  dev: venv
      ./venv/bin/uvicorn ngen_gitops.server:app --port 8080 --reload
  ```
  Target ini bergantung pada target `venv`, sehingga virtual environment akan dibuat otomatis jika belum ada.
- **Implikasi:** Hanya gunakan `make dev` untuk development. Untuk production, gunakan `gitops server` atau deployment dengan process manager (systemd, supervisord, dsb.).

---

### 7. Template Dinamis K8s-PR (Konfigurasi via .env)
- **Jenis:** Feature + Refactor
- **File:** `ngen_gitops/config.py`, `ngen_gitops/bitbucket.py`, `ngen_gitops/github.py`
- **Ringkasan:** Pola branch dan YAML path di workflow `k8s-pr` yang sebelumnya *hardcoded*, kini dapat dikustomisasi via variabel `.env`.
- **Detail:**

  **`config.py`:**
  - Ditambahkan section `k8s_pr` ke `load_config()` yang membaca:
    - `K8S_PR_BRANCH_TEMPLATE` (default: `{namespace}/{deploy}_deployment.yaml`)
    - `K8S_PR_YAML_TEMPLATE` (default: `{namespace}/{deploy}_deployment.yaml`)
    - `K8S_PR_REPO` (default: `gitops-k8s`)
  - Ditambahkan fungsi `get_k8s_pr_template() -> Dict[str, str]` sebagai accessor publik.
  - Komentar template ditambahkan di string `create_default_env()` sehingga otomatis tersedia di file `.env` baru.

  **`bitbucket.py` & `github.py`:**
  - Kedua file mengimpor `get_k8s_pr_template` dari `config`.
  - Fungsi `run_k8s_pr_workflow()` direfaktor:
    - Parameter `repo` diubah dari `str = "gitops-k8s"` menjadi `Optional[str] = None`.
    - Template di-*resolve* di awal fungsi menggunakan `str.format(**ctx)` dengan context `{cluster, namespace, deploy}`.
    - `effective_repo` diambil dari parameter `repo` jika diberikan, atau dari `K8S_PR_REPO` di config jika tidak.
    - Output log ditambahkan untuk menampilkan `Branch` dan `YAML path` yang digunakan.

- **Contoh konfigurasi custom:**
  ```bash
  # ~/.ngen-gitops/.env
  K8S_PR_BRANCH_TEMPLATE={cluster}/{namespace}/{deploy}
  K8S_PR_YAML_TEMPLATE=manifests/{namespace}/{deploy}_deploy.yaml
  K8S_PR_REPO=my-gitops-repo
  ```

- **Implikasi:**
  - **Backward compatible:** Jika tidak ada variabel K8S_PR_* di `.env`, perilaku default **identik** dengan sebelumnya.
  - **Placeholder tersedia:** `{cluster}`, `{namespace}`, `{deploy}` — sesuai argumen input `k8s-pr`.
  - Jika template menggunakan placeholder yang tidak valid (typo), Python akan raise `KeyError` saat runtime.
  - Endpoint API `/v1/gitops/k8s-pr` juga terpengaruh karena memanggil fungsi yang sama.

---

## Riwayat Versi Release Sebelumnya

| Versi | Commit | Tanggal | Keterangan |
|-------|--------|---------|------------|
| v0.1.16 | `0bd4dcd` | — | Release dengan Makefile |
| v0.1.15 | `f5cee59` | — | Rilis awal dengan fitur dasar |
| (dev) | `ddc4b92` | — | Commit pertama (`1st`) |

---

## Catatan untuk LLM / Developer Berikutnya

1. **Arsitektur Provider Pattern:** Provider (`bitbucket.py` / `github.py`) dipilih secara dinamis di `cli.py` berdasarkan nilai `GIT_DEFAULT_REMOTE` di config. Jika remote mengandung `"github"`, `github.py` digunakan; selainnya `bitbucket.py`.

2. **Config Priority:** Environment variables > `~/.ngen-gitops/.env` > nilai default di kode.

3. **Server vs CLI:** Logika bisnis ada di `bitbucket.py` / `github.py`. `cli.py` dan `server.py` hanyalah layer presentasi yang memanggil fungsi yang sama.

4. **Template Rendering:** Template K8s-PR menggunakan Python `str.format(**ctx)`. Placeholder harus berupa identifier Python yang valid dalam kurung kurawal.

5. **Lint errors dari Pyre2 adalah false-positive** — Pyre2 tidak dikonfigurasi dengan search root `venv/`, sehingga semua import third-party (fastapi, requests, pydantic, dll.) dilaporkan sebagai "not found". Gunakan `python3 -m py_compile` untuk validasi syntax yang sesungguhnya.
