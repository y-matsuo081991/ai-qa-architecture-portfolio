output "service_account_email" {
  description = "The email address of the created GCP Service Account."
  value       = google_service_account.github_actions_vqa.email
}

output "github_secrets_configured" {
  description = "The names of the secrets configured in the GitHub repository."
  value       = [
    github_actions_secret.gcp_credentials.secret_name,
    github_actions_secret.gcp_project_id.secret_name
  ]
}
