import pulumi
import pulumi_aws as aws

# Create an ECR repository
ecr_repository = aws.ecr.Repository(
    "ultratic-redux",
    image_tag_mutability="MUTABLE",  # Optional: Specify "IMMUTABLE" for immutable tags
    image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
        scan_on_push=True,  # Enable image scanning on push
    ),
    tags={
        "Environment": "Development", 
    }
)

# Lifecycle policy to get rid of old images
lifecycle_policy = aws.ecr.LifecyclePolicy(
    "ecr-lifecycle-policy",
    repository=ecr_repository.name,
    policy="""{
        "rules": [
            {
                "rulePriority": 1,
                "description": "Expire untagged images",
                "selection": {
                    "tagStatus": "untagged",
                    "countType": "imageCountMoreThan",
                    "countNumber": 10
                },
                "action": {
                    "type": "expire"
                }
            }
        ]
    }"""
)

# Apply the lifecycle policy
# repository_policy = aws.ecr.RepositoryPolicy(
#     "ecr-repository-policy",
#     repository=ecr_repository.name,
#     policy="""{
#         "Version": "2012-10-17",
#         "Statement": [
#             {
#                 "Effect": "Allow",
#                 "Principal": {
#                     "AWS": "arn:aws:iam::123456789012:role/MyRole"
#                 },
#                 "Action": [
#                     "ecr:GetDownloadUrlForLayer",
#                     "ecr:BatchGetImage",
#                     "ecr:BatchCheckLayerAvailability"
#                 ]
#             }
#         ]
#     }"""
# )

# Export the ECR repository URL
pulumi.export("ecr repo url", ecr_repository.repository_url)