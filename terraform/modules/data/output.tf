output "mlflow_user_data" {
  value = data.template_file.mlflow_user_data.rendered
}

output "ubuntu_ami_id" {
  value = data.aws_ami_ids.ubuntu_24.ids[0]
}

output "model_train_user_data" {
  value = data.template_file.model_train_user_data.rendered
}