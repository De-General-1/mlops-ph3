provider "aws" {
  alias   = "primary"
  region  = "eu-west-1"
  profile = "degen-mlops"
}

provider "aws" {
  alias   = "failover"
  region  = "us-east-1"
  profile = "degen-mlops"
}