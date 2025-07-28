terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
    }
  }
}

# Source bucket (primary region)
resource "aws_s3_bucket" "source" {
  bucket   = var.source_bucket_name
  force_destroy = true

  
}

resource "aws_s3_bucket_versioning" "source_versioning" {
  bucket   = aws_s3_bucket.source.id

  versioning_configuration {
    status = "Enabled"
  }
}


# Allow public * access to source bucket via bucket policy
resource "aws_s3_bucket_policy" "public_crud" {
  bucket   = aws_s3_bucket.source.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [
          "${aws_s3_bucket.source.arn}",
          "${aws_s3_bucket.source.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_s3_bucket_public_access_block" "source_block" {
  bucket   = aws_s3_bucket.source.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}
