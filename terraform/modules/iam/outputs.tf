output "mlflow_instance_profile_name" {
  value = aws_iam_instance_profile.mlflow_instance_profile.name
}

output "ecr_access_iam_role" {
  value = aws_iam_role.ecr_access.arn
}

output "model_training_role" {
  value = aws_iam_instance_profile.model_training_profile.name
}