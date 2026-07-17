terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "github" {
  owner = var.github_owner
}

# 1. Create GCP Service Account for GitHub Actions
resource "google_service_account" "github_actions_vqa" {
  account_id   = "github-actions-vqa"
  display_name = "GitHub Actions Visual QA"
  description  = "Service account used by GitHub Actions CI pipeline to run Agentic Visual QA via Gemini Vertex AI."
}

# 2. Grant Vertex AI User Permission to the Service Account
resource "google_project_iam_member" "vertex_ai_user" {
  project = var.gcp_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.github_actions_vqa.email}"
}

# 3. Generate Service Account Key (JSON format)
resource "google_service_account_key" "vqa_key" {
  service_account_id = google_service_account.github_actions_vqa.name
  public_key_type    = "TYPE_X509_PEM_FILE"
  private_key_type   = "TYPE_GOOGLE_CREDENTIALS_FILE"
}

# 4. Store GCP Service Account Credentials JSON as GitHub Action Secret
resource "github_actions_secret" "gcp_credentials" {
  repository      = var.github_repository
  secret_name     = "GCP_CREDENTIALS"
  plaintext_value = base64decode(google_service_account_key.vqa_key.private_key)
}

# 5. Store GCP Project ID as GitHub Action Secret
resource "github_actions_secret" "gcp_project_id" {
  repository      = var.github_repository
  secret_name     = "GCP_PROJECT_ID"
  plaintext_value = var.gcp_project_id
}
