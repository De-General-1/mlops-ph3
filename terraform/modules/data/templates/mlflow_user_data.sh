#!/bin/bash
set -e
# Update and install dependencies
export DEBIAN_FRONTEND=noninteractive
apt update -y
apt install -y python3-pip python3-venv nginx

# Setup mlflow environment
mkdir -p /opt/mlflow
cd /opt/mlflow
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install mlflow awscli boto3

# Create mlflow service user (optional)
useradd -m -s /bin/bash mlflow || true
chown -R mlflow:mlflow /opt/mlflow

# Start mlflow server
cat <<EOF > /etc/systemd/system/mlflow.service
[Unit]
Description=MLflow Tracking Server
After=network.target

[Service]
Type=simple
User=mlflow
WorkingDirectory=/opt/mlflow
Environment="MLFLOW_TRACKING_URI=http://localhost:5000"
ExecStart=/opt/mlflow/venv/bin/mlflow server --host 127.0.0.1 --port 5000 --default-artifact-root s3://mlflow-source-bucket-niico-phase3
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable mlflow
systemctl daemon-reexec
systemctl daemon-reload
systemctl enable mlflow
systemctl start mlflow

# Configure nginx as reverse proxy
cat <<EOF > /etc/nginx/sites-available/mlflow
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

# Enable the site and restart nginx
ln -s /etc/nginx/sites-available/mlflow /etc/nginx/sites-enabled/mlflow
rm /etc/nginx/sites-enabled/default || true
nginx -t && systemctl restart nginx
