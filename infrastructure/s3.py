import pulumi
import pulumi_aws as aws
import json

# Create S3 Bucket
s3_bucket = aws.s3.Bucket(
    "wiz-db-backups-for-me",
    bucket="wiz-db-backups-for-me",
    force_destroy=True,  # Optional: Allows bucket deletion even if it contains objects
)

# # Disable Block Public Access settings for the bucket
# public_access_block = aws.s3.BucketPublicAccessBlock("bucket-public-access-block",
#     bucket=s3_bucket.id,
#     block_public_policy=False,  # Allow public bucket policies
#     block_public_acls=False,   # Allow public ACLs
#     ignore_public_acls=False,   # Optional: Prevent ACLs from being ignored
#     restrict_public_buckets=False  # Allow public access for the bucket
# )


# Add a bucket policy for public read access
# s3_bucket_policy = aws.s3.BucketPolicy(
#     "wiz-db-backups-for-me-policy",
#     bucket=s3_bucket.id,
#     policy=s3_bucket.id.apply(
#         lambda bucket_name: json.dumps({
#             "Version": "2012-10-17",
#             "Statement": [
#                 {
#                     "Effect": "Allow",
#                     "Principal": "*",
#                     "Action": "s3:GetObject",
#                     "Resource": f"arn:aws:s3:::{bucket_name}/*"
#                 }
#             ]
#         })
#     )
# )

pulumi.export("s3_bucket_name", s3_bucket.bucket)