import os
import boto3


def handler(event, context):
    """Start the Airflow EC2 instance.

    The instance user_data boots Docker + Airflow automatically.
    After the DAG completes, the DAG's final task stops this instance.
    """
    ec2 = boto3.client("ec2", region_name=os.environ["REGION"])
    instance_id = os.environ["INSTANCE_ID"]

    ec2.start_instances(InstanceIds=[instance_id])

    return {
        "statusCode": 200,
        "body": f"Started instance {instance_id}",
    }
