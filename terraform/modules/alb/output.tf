output "http_alb_listener_arn" {
    value = aws_alb_listener.http_alb_listener.arn 
}

output "https_alb_listener_arn" {
    value = aws_alb_listener.https_alb_listener.arn
}

output "alb_dns" {
  value = aws_lb.alb.dns_name
}