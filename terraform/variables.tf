variable "gcp_project_id" {
  description = "The GCP Project ID to provision resources in."
  type        = string
}

variable "gcp_region" {
  description = "The default GCP region."
  type        = string
  default     = "asia-northeast1"
}

variable "github_owner" {
  description = "The GitHub username or organization owner of the repository."
  type        = string
  default     = "y-matsuo081991"
}

variable "github_repository" {
  description = "The GitHub repository name to set Actions secrets on."
  type        = string
  default     = "ai-qa-architecture-portfolio"
}
