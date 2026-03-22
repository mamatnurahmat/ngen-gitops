# Product Requirements Document (PRD) - ngen-gitops

> **Versi Dokumen:** 1.1
> **Diperbarui:** 2026-03-23

---

## 1. Introduction

**ngen-gitops** adalah sebuah tool berbasis Python (tersedia sebagai CLI dan Web Server) yang dirancang untuk mengotomatisasi operasi GitOps di berbagai Git provider (GitHub, Bitbucket, GitLab). Tool ini memungkinkan manajemen *branch*, pembaruan *image* pada file manifest Kubernetes (YAML), dan pembuatan serta pengelolaan *Pull Request* yang efisien, baik dalam lingkungan CI/CD lokal maupun *server-based*.

---

## 2. Product Vision & Goals

- **Visi:** Menyederhanakan dan mengotomatisasi alur kerja rilis dan deployment ke Kubernetes tanpa harus bergantung pada antarmuka web repository, semuanya dapat diakses melalui CLI yang ringan atau REST API yang andal.
- **Tujuan:**
  - Mendukung multi-provider Git (GitHub, Bitbucket, GitLab) dengan transisi mulus.
  - Meningkatkan kecepatan update *image* pada *environment* Kubernetes berbasis GitOps.
  - Menyediakan REST API server agar dapat diintegrasikan ke platform lain atau dipanggil melalui *webhook*.
  - Memberikan template yang dapat dikonfigurasi untuk workflow K8s PR tanpa perlu perubahan kode.

---

## 3. Target Audience

- DevOps Engineers / Site Reliability Engineers (SRE).
- Software Engineers yang ingin menyederhanakan siklus *deployment*.
- Tim pengembang yang menggunakan pola GitOps untuk *Infrastructure as Code* (IaC) atau manifest Kubernetes.

---

## 4. Key Features & Requirements

### 4.1. General Git Operations (Multi-Remote)
- **Support Provider:** Bitbucket (App Passwords), GitHub (PAT), GitLab.
- **Fitur Dasar:** `clone`, `pull`, `push`, `fetch`, `commit`, `status`.
- **Autentikasi Pintar:** Mendukung pembacaan *credentials* dari `~/.netrc`, `~/.ngen-gitops/.env`, maupun *environment variables*.

### 4.2. GitOps Automations
- **Branch Management:** Membuat branch baru dari sebuah referensi (source branch).
- **YAML Image Updater:** Memodifikasi referensi *image container* dalam manifest Kubernetes (file YAML), melakukan *commit*, dan men-*push* perubahan secara otomatis (mendukung mode *dry-run*).
- **Pull Request Management:** Membuat dan men-*merge* PR, menampilkan daftar PR beserta status (open, merged, declined) dan *diff* secara langsung di terminal.
- **Kubernetes Workflow (K8s-PR):** Fitur interaktif dan non-interaktif terpadu yang menggabungkan semua aksi menjadi satu alur (Create Branch → Update Image → Create PR → Merge Opsional).
- **Template Dinamis K8s-PR:** Branch name, YAML path, dan nama repo dapat dikustomisasi melalui `.env` menggunakan placeholder `{cluster}`, `{namespace}`, `{deploy}`.
- **File & Tag Management:** Mengambil konten file spesifik (`get-file`), melihat commit history (`logs`), hingga mengelola webhook repository.

### 4.3. REST API Web Server (FastAPI)
- **Mode Server:** Berjalan sebagai daemon API berbasis Python ASGI (`uvicorn` + `FastAPI`).
- **Root Redirect ke Swagger:** Akses ke root URL `/` otomatis redirect ke `/docs` (Swagger UI).
- **Endpoints Utama:**

| Method | Path | Deskripsi |
|--------|------|-----------|
| `GET` | `/` | Redirect ke Swagger UI `/docs` |
| `GET` | `/health` | Health check |
| `GET` | `/config` | Tampilkan konfigurasi aktif (password disamarkan) |
| `GET` | `/api/sample` | Sample API untuk demo Swagger |
| `POST` | `/v1/gitops/create-branch` | Buat branch baru |
| `POST` | `/v1/gitops/set-image-yaml` | Update image di YAML |
| `POST` | `/v1/gitops/pull-request` | Buat Pull Request |
| `POST` | `/v1/gitops/merge` | Merge Pull Request |
| `POST` | `/v1/gitops/k8s-pr` | Jalankan workflow K8s lengkap |

### 4.4. Notifications
- **Microsoft Teams Webhook Support:** Apabila *webhook URI* dikonfigurasikan, setiap tindakan krusial (create branch, image update, PR) otomatis mengirimkan notifikasi.

### 4.5. Konfigurasi Template K8s-PR (Fitur Baru)
Workflow `k8s-pr` mendukung template dinamis yang dapat dikonfigurasi melalui `~/.ngen-gitops/.env`:

```bash
# Template untuk nama branch yang dibuat (placeholders: {cluster}, {namespace}, {deploy})
K8S_PR_BRANCH_TEMPLATE={namespace}/{deploy}_deployment.yaml

# Template untuk path file YAML yang diupdate
K8S_PR_YAML_TEMPLATE={namespace}/{deploy}_deployment.yaml

# Repository default untuk workflow k8s-pr
K8S_PR_REPO=gitops-k8s
```

Makna parameter:
- `cluster` = nama branch sumber di repository (e.g., nama cluster Kubernetes)
- `namespace` = subfolder di root repository GitOps
- `deploy` = nama deployment, digunakan sebagai prefix nama file YAML

---

## 5. Non-Functional Requirements (NFR)

- **Performa:** Command CLI harus direspons dalam hitungan detik.
- **Keamanan:** Endpoint `/config` menyembunyikan nilai sensitif (token, password) dengan masking `***SET***`.
- **Toleransi Kesalahan:** Memberikan pesan error yang jelas ketika autentikasi gagal, format YAML keliru, atau repositori remote salah konfigurasi.
- **Portabilitas:** Mudah di-deploy melalui PyPI (`pip install ngen-gitops`) maupun `pipx`.
- **Developer Experience:** Mode development dengan `make dev` untuk menjalankan server dengan hot-reload otomatis.

---

## 6. Development & Deployment

- Dibangun dengan Python `>3.7`.
- *Dependencies*: `requests`, `fastapi`, `uvicorn`, `pyyaml`, `python-dotenv`.
- Konfigurasi rilis publik pada PyPI: `pip install ngen-gitops`.
- Perintah `make dev` untuk menjalankan server development dengan reload otomatis.

---

## 7. Future Roadmap

- Menambahkan implementasi API penuh untuk GitLab.
- Memperkuat kontrol pengalihan environment variabel Kubernetes dan kustomisasi manifest Helm.
- Menambahkan endpoint API untuk operasi `tag`, `logs`, dan `get-file`.
- Mendukung multiple templates K8s-PR berdasarkan konteks yang berbeda (per-cluster, per-environment).
