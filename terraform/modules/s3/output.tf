output "s3_bucket_id" {
    value = aws_s3_bucket.source.id
}

output "s3_bucket_arn" {
    value = aws_s3_bucket.source.arn
}

output "bucket_name" {
    value = aws_s3_bucket.source.bucket
}
