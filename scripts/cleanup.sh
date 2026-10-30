#!/usr/bin/env bash
# DESTRUCTIVE: deletes the whole stack (API, Lambdas, DynamoDB table + all data, SNS topic, S3 buckets).
#   AWS_PROFILE=pm-project AWS_REGION=ap-south-1 ./scripts/cleanup.sh
set -euo pipefail
: "${AWS_PROFILE:?Set AWS_PROFILE}"
: "${AWS_REGION:?Set AWS_REGION}"
STACK_NAME="${STACK_NAME:-pm-aws}"

aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" --query '{Account:Account,Arn:Arn}' --output table
echo "This will permanently delete stack '$STACK_NAME' and all its data in region $AWS_REGION."
read -r -p "Type the stack name to confirm: " typed
[ "$typed" = "$STACK_NAME" ] || { echo "Aborted."; exit 1; }

for key in FrontendBucketName DataBucketName; do
  b="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --profile "$AWS_PROFILE" --region "$AWS_REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='$key'].OutputValue" --output text)"
  if [ -n "$b" ] && [ "$b" != "None" ]; then
    echo "Emptying s3://$b"
    aws s3 rm "s3://$b" --recursive --profile "$AWS_PROFILE" --region "$AWS_REGION" || true
  fi
done
aws cloudformation delete-stack --stack-name "$STACK_NAME" --profile "$AWS_PROFILE" --region "$AWS_REGION"
aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --profile "$AWS_PROFILE" --region "$AWS_REGION"
echo "Stack deleted. (The SAM-managed artifact bucket 'aws-sam-cli-managed-default' is shared and left in place.)"
