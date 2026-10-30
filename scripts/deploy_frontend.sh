#!/usr/bin/env bash
# Build the React dashboard, point it at the deployed API, and upload it to the S3 website bucket.
#   AWS_PROFILE=pm-project AWS_REGION=ap-south-1 ./scripts/deploy_frontend.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${AWS_PROFILE:?Set AWS_PROFILE}"
: "${AWS_REGION:?Set AWS_REGION}"
STACK_NAME="${STACK_NAME:-pm-aws}"

out() {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
API_URL="$(out ApiUrl)"
BUCKET="$(out FrontendBucketName)"
SITE_URL="$(out FrontendUrl)"
echo "API: $API_URL"; echo "Bucket: $BUCKET"

printf '{ "apiBaseUrl": "%s" }\n' "$API_URL" > frontend/public/config.json
(cd frontend && npm ci --no-audit --no-fund && npm run build)
aws s3 sync frontend/dist "s3://$BUCKET" --delete --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --cache-control "no-cache"
echo "Dashboard: $SITE_URL"
# Reset the committed placeholder so no deployment URL is stored in git
printf '{ "apiBaseUrl": "" }\n' > frontend/public/config.json
