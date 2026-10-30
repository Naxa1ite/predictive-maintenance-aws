#!/usr/bin/env bash
# Deploy (or update) the backend stack. Creates billable-capable AWS resources:
# review docs/aws-deployment.md first. Asks for confirmation before changing anything.
#
#   AWS_PROFILE=pm-project AWS_REGION=ap-south-1 ALERT_EMAIL=you@example.com ./scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${AWS_PROFILE:?Set AWS_PROFILE (e.g. pm-project)}"
: "${AWS_REGION:?Set AWS_REGION (e.g. ap-south-1)}"
STACK_NAME="${STACK_NAME:-pm-aws}"
PROJECT_NAME="${PROJECT_NAME:-pm-aws}"
ALERT_EMAIL="${ALERT_EMAIL:-}"
ALERT_THRESHOLD="${ALERT_THRESHOLD:-}"
SAM="${SAM:-.venv/Scripts/sam.exe}"
[ -x "$SAM" ] || SAM="sam"

echo "Active identity (no credentials shown):"
aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" --query '{Account:Account,Arn:Arn}' --output table
echo "Stack: $STACK_NAME   Region: $AWS_REGION   Alert email: ${ALERT_EMAIL:-<none, subscribe manually>}"
read -r -p "Deploy to the account above? Type 'yes' to continue: " ok
[ "$ok" = "yes" ] || { echo "Aborted."; exit 1; }

"$SAM" build --template-file backend/template.yaml --build-dir backend/.aws-sam/build
"$SAM" deploy \
  --template-file backend/.aws-sam/build/template.yaml \
  --stack-name "$STACK_NAME" --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --capabilities CAPABILITY_IAM --resolve-s3 --confirm-changeset --no-fail-on-empty-changeset \
  --parameter-overrides "ProjectName=$PROJECT_NAME" "AlertEmail=$ALERT_EMAIL" "AlertThreshold=$ALERT_THRESHOLD"

aws cloudformation describe-stacks --stack-name "$STACK_NAME" --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output table
echo "If you set ALERT_EMAIL, open the 'AWS Notification - Subscription Confirmation' email and click Confirm."
