import json
import pulumi
import pulumi_aws as aws

# S3 Bucket for AWS Config
config_bucket = aws.s3.Bucket(
    "configBucket",
    bucket_prefix="aws-config-",
    acl="private",
    force_destroy=True
)

# Bucket policy to allow AWS Config to write to the bucket
bucket_policy = aws.s3.BucketPolicy(
    "configBucketPolicy",
    bucket=config_bucket.id,
    policy=config_bucket.id.apply(lambda bucket_id: json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "config.amazonaws.com"},
                "Action": "s3:PutObject",
                "Resource": f"arn:aws:s3:::{bucket_id}/*",
                "Condition": {
                    "StringEquals": {
                        "s3:x-amz-acl": "bucket-owner-full-control"
                    }
                }
            },
            {
                "Effect": "Allow",
                "Principal": {"Service": "config.amazonaws.com"},
                "Action": "s3:GetBucketAcl",
                "Resource": f"arn:aws:s3:::{bucket_id}"
            }
        ]
    }))
)

# IAM Role for AWS Config
config_role = aws.iam.Role(
    "configRole",
    assume_role_policy=aws.iam.get_policy_document(
        statements=[
            {
                "effect": "Allow",
                "principals": [{"type": "Service", "identifiers": ["config.amazonaws.com"]}],
                "actions": ["sts:AssumeRole"] 
            }
        ]
    ).json
)

aws.iam.RolePolicyAttachment(
    "configRoleAttachment",
    role=config_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
)

# Configuration Recorder
config_recorder = aws.cfg.Recorder(
    "configRecorder",
    role_arn=config_role.arn,
    recording_group={
        "all_supported": True,
        "include_global_resource_types": True
    }
)

# Delivery Channel
config_delivery_channel = aws.cfg.DeliveryChannel(
    "configDeliveryChannel",
    s3_bucket_name=config_bucket.bucket,
    snapshot_delivery_properties=aws.cfg.DeliveryChannelSnapshotDeliveryPropertiesArgs(
        delivery_frequency="One_Hour"
    )
)

# Start the Config recorder once the delivery channel is ready
recorder_status = aws.cfg.RecorderStatus(
    "recorderEnable",
    name=config_recorder.name,
    is_enabled=True,
    opts=pulumi.ResourceOptions(depends_on=config_delivery_channel)
)

# Config Rule: Prohibit Public Read for S3 Buckets
s3_public_read_prohibited_rule = aws.cfg.Rule(
    "s3PublicReadProhibitedRule",
    source=aws.cfg.RuleSourceArgs(
        owner="AWS",
        source_identifier="S3_BUCKET_PUBLIC_READ_PROHIBITED"
    ),
    opts=pulumi.ResourceOptions(depends_on=config_recorder)
)