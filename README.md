# Predictive Maintenance of Industrial Machinery Using AWS and Machine Learning

A serverless prototype that estimates machine failure risk from sensor readings: Random Forest model in AWS Lambda, API Gateway,
DynamoDB, SNS email alerts, CloudWatch, and a React dashboard on S3. **Academic prototype.** Outputs are model predictions, not confirmed
failures; the dataset is synthetic; not suitable for safety-critical use.

## Results (held-out test set, 2,000 rows, 68 failures)

Random Forest, threshold 0.48 (chosen on validation): precision 0.885, recall 0.794, F1 0.837, ROC-AUC 0.982
(TN 1925, FP 7, FN 14, TP 54). Details and model comparison: `docs/project-report.md`, `ml/artifacts/metrics.json`.
High scores partly reflect that AI4I failures are generated from physical rules; see the limitations section.

## Structure

| Path | Purpose |
|---|---|
| `ml/` | preprocessing, training, evaluation, artifacts (`train.py` retrains and exports the model) |
| `backend/` | SAM template, Lambda code (`src/`), tests |
| `frontend/` | React + Vite dashboard (plain CSS, Recharts) |
| `simulator/` | synthetic scenario generator (CLI; the dashboard has the same controls) |
| `scripts/` | train, deploy, deploy_frontend, cleanup |

## Run locally (no AWS needed)

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt     # Linux/macOS: .venv/bin/python
.venv/Scripts/python.exe ml/train.py                            # downloads data, trains, writes ml/artifacts + Lambda model
.venv/Scripts/python.exe -m pytest -q                           # 43 tests
.venv/Scripts/python.exe simulator/simulator.py --dry-run --scenarios normal elevated high --rounds 10 --interval 0
cd frontend && npm install && npm test && npm run dev          # dashboard; with no API configured use "Demo mode" (labelled synthetic)
```

## Deploy to AWS (creates billable-capable resources; read `docs/aws-deployment.md` first)

```bash
aws configure --profile pm-project
AWS_PROFILE=pm-project AWS_REGION=ap-south-1 ALERT_EMAIL=you@example.com ./scripts/deploy.sh
AWS_PROFILE=pm-project AWS_REGION=ap-south-1 ./scripts/deploy_frontend.sh
```

Update after changes: re-run the same commands (retrain first with `./scripts/train_model.sh` if the model changed).

## Try the live stack

```bash
python simulator/simulator.py --api-url <ApiUrl> --scenarios normal elevated high --rounds 10 --interval 2
```

## Clean up (destructive)

```bash
AWS_PROFILE=pm-project AWS_REGION=ap-south-1 ./scripts/cleanup.sh
```

## Notes

No AWS keys are stored in this repo; credentials come from the AWS CLI profile. `.env.example` lists configurable names.
Dataset: AI4I 2020 (UCI, DOI 10.24432/C5HS5C, CC BY 4.0).
