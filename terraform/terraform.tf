terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }

  backend "s3" {
    bucket       = "phase3-mlops-tf-state-bucket-degen-1"
    key          = "terraform.tfstate"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true
    profile      = "degen-mlops"
  }
}