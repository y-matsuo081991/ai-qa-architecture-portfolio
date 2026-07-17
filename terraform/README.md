# 🌐 Infrastructure as Code (IaC): GCP & GitHub Sync via Terraform

This directory contains the production-grade Terraform configurations to automate the entire onboarding pipeline of our **Agentic Visual QA Engine**. 

Rather than manually running commands or clicking through GCP & GitHub dashboards, this IaC setup codifies the standard enterprise practice of **declarative resource management**.

---

## 🏗️ What This Code Does

By running this Terraform configuration, you automate:
1. **GCP Service Account Provisioning:** Creates a dedicated GCP service account (`github-actions-vqa`) designed strictly for visual QA audits.
2. **IAM Role Assignment:** Binds the `roles/aiplatform.user` (Vertex AI User) role to the service account, granting it permission to call Google Gemini Vertex APIs while maintaining the Principle of Least Privilege (PoLP).
3. **Cryptographic Key Generation:** Dynamically generates a secure, one-shot private JSON credentials key for the service account.
4. **GitHub Secrets Synchronization:** Automatically feeds the generated GCP JSON credentials (`GCP_CREDENTIALS`) and the target project ID (`GCP_PROJECT_ID`) directly into your GitHub repository's Action secrets securely.

---

## 🛠️ Prerequisites & Setup

Ensure you have the following installed on your local machine:
* [Terraform](https://developer.hashicorp.com/terraform/downloads) (>= 1.5.0)
* [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install)
* [GitHub CLI (gh)](https://cli.github.com/)

### 1. Authenticate with Google Cloud
Ensure your local terminal is authenticated as an administrator capable of managing IAM on your target project:
```bash
gcloud auth login
gcloud config set project your-gcp-project-id
gcloud auth application-default login
```

### 2. Obtain GitHub Token
The Terraform GitHub Provider requires a Personal Access Token (PAT) or a local session token to write repository secrets. You can dynamically export your current authenticated GitHub CLI token:
```bash
export GITHUB_TOKEN=$(gh auth token)
```

---

## 🚀 Execution Steps

### Step 1: Initialize Variables
Copy the template variable file and fill in your GCP project and GitHub repository specifics:
```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit the newly created `terraform.tfvars`:
```hcl
gcp_project_id    = "matsuo-agent-dev"
gcp_region        = "asia-northeast1"
github_owner      = "y-matsuo081991"
github_repository = "ai-qa-architecture-portfolio"
```

### Step 2: Initialize & Apply
Initialize the Terraform working directory (installs provider dependencies):
```bash
terraform init
```

Preview the execution plan (dry-run):
```bash
terraform plan
```

Execute the plan to provision resources and bind secrets:
```bash
terraform apply
```

To teardown the service account and clean up secrets from GitHub:
```bash
terraform destroy
```

---

## 🔒 Security Best Practices Implemented

* **Least Privilege (IAM):** The service account is only granted `roles/aiplatform.user`—preventing it from altering code, accessing billing, or reading other databases.
* **Declarative Key Lifecycles:** Keys are managed via Terraform state. If you run `terraform destroy`, the key is revoked on Google Cloud and safely purged from GitHub Secrets.
* **No Local State Storage (Recommendation):** In production environments, configure a remote state backend (e.g., GCS Bucket with state locking) to keep your Terraform state encrypted and accessible by team members.
