# Product Requirements Document (PRD) - ngen-gitops

## 1. Introduction
**ngen-gitops** adalah sebuah tool berbasis Python (tersedia sebagai CLI dan Web Server) yang dirancang untuk mengotomatisasi operasi GitOps di berbagai Git provider (GitHub, Bitbucket, GitLab). Tool ini memungkinkan manajemen *branch*, pembaruan *image* pada file manifest Kubernetes (YAML), dan pembuatan serta pengelolaan *Pull Request* yang sangat efisien dan terintegrasi, baik dalam lingkungan CI/CD lokal maupun *server-based*.

## 2. Product Vision & Goals
*   **Visi:** Menyederhanakan dan mengotomatisasi alur kerja rilis dan deployment ke Kubernetes tanpa harus bergantung pada antarmuka web repository, semuanya dapat diakses melalui CLI yang ringan atau API yang andal.
*   **Tujuan:**
    *   Mendukung multi-provider Git (GitHub, Bitbucket, GitLab) dengan transisi mulus.
    *   Meningkatkan kecepatan update *image* pada *environment* Kubernetes berbasis GitOps.
    *   Menyediakan REST API server agar dapat diintegrasikan kedalam platform lain atau dipanggil melalui *webhook*.

## 3. Target Audience
*   DevOps Engineers / Site Reliability Engineers (SRE).
*   Software Engineers yang ingin menyederhanakan siklus *deployment*.
*   Tim pengembang yang menggunakan pola GitOps untuk *Infrastructure as Code* (IaC) atau manifest Kubernetes.

## 4. Key Features & Requirements

### 4.1. General Git Operations (Multi-Remote)
*   **Support Provider:** Bitbucket (App Passwords), GitHub (PAT), GitLab.
*   **Fitur Dasar:** `clone`, `pull`, `push`, `fetch`, `commit`, `status`.
*   **Authentikasi Pintar:* Mendukung pembacaan *credentials* dari `~/.netrc`, `~/.ngen-gitops/.env`, maupun *environment variables*.

### 4.2. GitOps Automations
*   **Branch Management:** Membuat branch baru dari sebuah referensi (source branch).
*   **YAML Image Updater:** Memodifikasi referensi *image container* dalam manifest Kubernetes (file YAML), melakukan *commit*, dan men-*push* perubahan tersebut secara otomatis (mendukung mode *dry-run*).
*   **Pull Request Management:** Membuat dan menggabungkan (*merge*) *Pull Request*, serta menampilkan daftar PR beserta status (open, merged, declined) dan *Diff* secara langsung di terminal.
*   **Kubernetes Workflow (K8s-PR):** Fitur interaktif dan non-interaktif terpadu yang menggabungkan semua aksi menjadi satu alur (Create Branch -> Update Image -> Create PR -> Merge Opsional).
*   **File & Tag Management:** Mengambil data spesifik (get-file), melihat status history commit (logs), hingga mengelola (create/delete) webhook repository.

### 4.3. REST API Web Server (FastAPI)
*   **Mode Server:** Berjalan sebagai daemon API berbasis Python ASGI (`uvicorn` + `FastAPI`).
*   **Automatic Docs (Swagger & ReDoc):** Tersedia default di root address (`/`) atau `/docs` berisi Sample API dan Endpoint Definition.
*   **Endpoints Utama:**
    *   `POST /v1/gitops/create-branch`
    *   `POST /v1/gitops/set-image-yaml`
    *   `POST /v1/gitops/pull-request`
    *   `POST /v1/gitops/merge`
    *   `POST /v1/gitops/k8s-pr`
    *   `GET /api/sample` (Sample API endpoint)

### 4.4. Notifications
*   **Microsoft Teams Webhook Support:** Apabila *webhook URI* dikonfigurasikan, setiap tindakan krusial (seperti *create branch*, *image update*, atau aksi PR) otomatis akan mengirimkan pesan notifikasi.

## 5. Non-Functional Requirements (NFR)
*   **Performa:** Command CLI harus direspons dalam hitungan detik.
*   **Toleransi Kesalahan & Keterbacaan:** Harus menyertakan respon *error message* yang interaktif ketika autentikasi gagal, format YAML keliru, atau repositori remote salah konfigurasi.
*   **Portabilitas:** Mudah di-deploy melalui modul PyPI (`pip install`) maupun `pipx` yang berjalan pada virtual environment terisolasi.

## 6. Development & Deployment
*   Dibangun dengan Python `>3.7`.
*   *Dependencies* Minimum: `requests`, `fastapi`, `uvicorn`, `pyyaml`, `python-dotenv`.
*   Konfigurasi rilis publik pada PyPI dengan format `pip install ngen-gitops`.

## 7. Future Roadmap
*   Menambahkan implementasi API khusus untuk GitLab API operations (*currently wrapper support*).
*   Memperkaya *dashboard* operasional dari Swagger Docs.
*   Memperkuat kontrol pengalihan environment variabel Kubernetes dan kustomisasi manifest Helm.
