import os

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ.pop("AWS_PROFILE", None)

import boto3  # noqa: E402
import pytest  # noqa: E402
from moto import mock_aws  # noqa: E402


@pytest.fixture
def aws(monkeypatch):
    with mock_aws():
        ddb = boto3.client("dynamodb")
        ddb.create_table(
            TableName="t", BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("pk", "sk", "gsi1pk", "gsi1sk")],
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            GlobalSecondaryIndexes=[{"IndexName": "gsi1", "Projection": {"ProjectionType": "ALL"},
                                     "KeySchema": [{"AttributeName": "gsi1pk", "KeyType": "HASH"},
                                                   {"AttributeName": "gsi1sk", "KeyType": "RANGE"}]}])
        sns = boto3.client("sns")
        arn = sns.create_topic(Name="alerts")["TopicArn"]
        sqs = boto3.client("sqs")
        q = sqs.create_queue(QueueName="capture")["QueueUrl"]
        qarn = sqs.get_queue_attributes(QueueUrl=q, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
        sns.subscribe(TopicArn=arn, Protocol="sqs", Endpoint=qarn)
        monkeypatch.setenv("TABLE_NAME", "t")
        monkeypatch.setenv("ALERT_TOPIC_ARN", arn)
        monkeypatch.setenv("ALERT_THRESHOLD", "")
        monkeypatch.setenv("ALERT_COOLDOWN_MINUTES", "30")
        yield {"sqs": sqs, "queue": q}


def sent_alerts(aws):
    msgs = aws["sqs"].receive_message(QueueUrl=aws["queue"], MaxNumberOfMessages=10).get("Messages", [])
    return len(msgs)
