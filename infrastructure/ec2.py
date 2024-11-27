import pulumi
import json
import pulumi_aws as aws
from network import public_subnet_a, vpc
from s3 import s3_bucket

# Load Pulumi configuration and needed variables
config = pulumi.Config()
git_repo_url = config.require("git_repo_url")
s3_bucket_name = config.require("s3_bucket")
vpc_cidr_block = config.require_object("vpc")["cidr_block"]

# AMI Lookup
ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["amazon"],
    filters=[{"name": "name", "values": ["amzn2-ami-hvm-*-x86_64-gp2"]}]
)

# Create an IAM Role for EC2
role = aws.iam.Role("ec2InstanceRole",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }"""
)

# Create an IAM Policy that grants permissions to upload to S3
policy_object = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:PutObject",
            "Resource": f"arn:aws:s3:::{s3_bucket_name}/*"
        },
        {
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": f"arn:aws:s3:::{s3_bucket_name}"
        }
    ]
}
policy = aws.iam.Policy("ec2S3UploadPolicy",
    description="Policy that allows EC2 to upload to a specific S3 bucket",
    policy=json.dumps(policy_object)
)

# Attach the policy to the role
role_policy_attachment = aws.iam.RolePolicyAttachment("rolePolicyAttachment",
    role=role.name,
    policy_arn=policy.arn
)

# Create instance profile
instance_profile = aws.iam.InstanceProfile("ec2-s3-instance-profile",
    role=role.name
)

# Security Group for db-instance
db_instance_sg = aws.ec2.SecurityGroup(
    "db-instance-sg",
    vpc_id=vpc.id,
    description="Security Group for db-instance",
    egress=[
        {
            "protocol": "-1",  # This allows all protocols
            "from_port": 0,    # Start of the port range
            "to_port": 0,      # End of the port range
            "cidr_blocks": ["0.0.0.0/0"]  # Allow all outbound traffic
        }
    ]
)

# Allow port 22 from anywhere
aws.ec2.SecurityGroupRule(
    "db-instance-ssh",
    type="ingress",
    from_port=22,
    to_port=22,
    protocol="tcp",
    security_group_id=db_instance_sg.id,
    cidr_blocks=["0.0.0.0/0"]
)

# Allow port 5432 from within the VPC
aws.ec2.SecurityGroupRule(
    "db-instance-postgres",
    type="ingress",
    from_port=5432,
    to_port=5432,
    protocol="tcp",
    security_group_id=db_instance_sg.id,
    cidr_blocks=[vpc.cidr_block]
)

# user_data Script
user_data_script = f"""#!/bin/bash
# Update packages and install Ansible
yum update -y
amazon-linux-extras enable ansible2
yum install -y ansible git

# Fetch Ansible playbook from configured repo
git clone {git_repo_url} /tmp/wiz-stack

# CD and create dynamic vars file
cd /tmp/wiz-stack/playbooks
cat <<EOF > dynamic-vars.yml
---
s3_bucket_name: {s3_bucket_name}
vpc_cidr: {vpc_cidr_block}
EOF

# Run the playbooks
ansible-playbook -e @dynamic-vars.yml postgres-install.yml
ansible-playbook -e @dynamic-vars.yml s3-backup.yml
ansible-playbook -e @dynamic-vars.yml restrict-access.yml
"""

db_instance = aws.ec2.Instance(
    "db-instance",
    ami=ami.id,
    instance_type="t3.medium",
    subnet_id=public_subnet_a.id,
    vpc_security_group_ids=[db_instance_sg.id],
    iam_instance_profile=instance_profile.name,
    key_name="my-mbp",
    user_data=user_data_script,
    tags={"Name": "db-instance"}
)

pulumi.export("db_instance_public_dns", db_instance.public_dns)
pulumi.export("user-data", user_data_script)
pulumi.export("policy", policy)