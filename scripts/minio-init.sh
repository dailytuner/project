#!/bin/sh
set -e

echo '⏳ Waiting for MinIO...';
sleep 10;

# Читаем секреты
ROOT_PASS=$(cat /run/secrets/minio-root-password | tr -d '\n\r')
S3_ACCESS=$(cat /run/secrets/s3-access-key | tr -d '\n\r')
S3_SECRET=$(cat /run/secrets/s3-secret-key | tr -d '\n\r')

if [ -z "$ROOT_PASS" ] || [ -z "$S3_ACCESS" ] || [ -z "$S3_SECRET" ]; then
  echo '❌ ERROR: Empty credentials from secrets'
  exit 1
fi

echo '⏳ Configuring MinIO client...';
mc alias set myminio http://minio:9000 paadmin "$ROOT_PASS" --api S3v4;

BUCKET="personal-assistant-lake";

# Создаем бакет
if mc ls myminio/$BUCKET > /dev/null 2>&1; then
  echo '✅ Bucket exists';
else
  echo '📦 Creating bucket...';
  mc mb myminio/$BUCKET;
  mc anonymous set private myminio/$BUCKET;
fi

# Включаем версионирование
echo '📋 Enabling versioning...';
mc version enable myminio/$BUCKET;

# Lifecycle (проверка без grep)
echo '📋 Setting lifecycle policy (90 days for psych/)...';
mc ilm add myminio/$BUCKET --prefix "psych/" --expiry-days "90" 2>/dev/null || echo '✅ Lifecycle already exists';

# Создаем сервисного пользователя
echo '👤 Creating service user: psych-lake';
mc admin user add myminio "$S3_ACCESS" "$S3_SECRET" 2>/dev/null || echo '✅ User already exists';

# Создаем политику
echo '📋 Creating policy...';
cat > /tmp/policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::personal-assistant-lake",
        "arn:aws:s3:::personal-assistant-lake/*"
      ]
    }
  ]
}
EOF

mc admin policy create myminio psych-policy /tmp/policy.json 2>/dev/null || echo '✅ Policy already exists';
mc admin policy attach myminio psych-policy --user "$S3_ACCESS" 2>/dev/null || echo '✅ Policy already attached';

echo '📋 Bucket info:';
mc ls myminio/;
mc stat myminio/$BUCKET;

touch /tmp/init-completed;
echo '✅ MinIO initialization completed successfully!';
exit 0;
