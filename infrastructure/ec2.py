import pulumi
import json
import pulumi_aws as aws
from network import public_subnet_a, vpc, private_zone
from k8s import secret_version

# Load Pulumi configuration and needed variables
config = pulumi.Config()
git_repo_url = config.require("git_repo_url")
s3_bucket_name = config.require("s3_bucket")
vpc_cidr_block = config.require_object("vpc")["cidr_block"]
internal_domain = config.require("internal_domain")
db_instance_name = config.require("db_instance")
web_app_config = config.require_object("web_app")

# Get AWS caller identity
caller_identity = aws.get_caller_identity()

# AMI Lookup
ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["amazon"],
    filters=[{"name": "name", "values": ["al2023-ami-2023*-x86_64"]}]
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

# Create an IAM Policy that grants necessary permissions to db instance
policy_object = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "ec2:*",
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": "s3:PutObject",
            "Resource": f"arn:aws:s3:::{s3_bucket_name}/*"
        },
        {
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": f"arn:aws:s3:::{s3_bucket_name}"
        },
        {
            "Effect": "Allow",
            "Action": "secretsmanager:GetSecretValue",
            "Resource": f"arn:aws:secretsmanager:{aws.config.region}:{caller_identity.account_id}:secret:{web_app_config.get("name")}*"
        }
    ]
}

policy = aws.iam.Policy("db-instance-extra-perms",
    description="Policy that allows instance to access S3 bucket for backups, needed secrets and all ec2",
    policy=json.dumps(policy_object)
)

# Attach the policy to the role
role_policy_attachment = aws.iam.RolePolicyAttachment("db-instance-extra-perms-rpa",
    role=role.name,
    policy_arn=policy.arn
)

# Create instance profile
instance_profile = aws.iam.InstanceProfile("ec2-instance-profile",
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
yum install -y ansible git

# Fetch Ansible playbook from configured repo
git clone {git_repo_url} /tmp/wiz-stack

# CD and create dynamic vars file
cd /tmp/wiz-stack/playbooks
cat <<EOF > dynamic-vars.yml
---
s3_bucket_name: {s3_bucket_name}
vpc_cidr: {vpc_cidr_block}
postgres_secret_name: {web_app_config.get("postgres_secret")}
aws_region: {aws.config.region}
EOF

# Install postgres and other needed packages
ansible-playbook -e @dynamic-vars.yml install-packages.yml

# Install community.postgresql ansible collection
ansible-galaxy collection install community.postgresql

# Setup s3 backup routine
ansible-playbook -e @dynamic-vars.yml s3-backup.yml

# Setup postgres access rules and users
ansible-playbook -e @dynamic-vars.yml postgres-access.yml
"""

db_instance = aws.ec2.Instance(
    db_instance_name,
    ami=ami.id,
    instance_type="t3.medium",
    root_block_device={
        "volume_size": 20,  # Size in GiB
        "volume_type": "gp2",  # General Purpose SSD
        "delete_on_termination": True,  # Automatically delete the volume on instance termination
    },
    subnet_id=public_subnet_a.id,
    vpc_security_group_ids=[db_instance_sg.id],
    iam_instance_profile=instance_profile.name,
    key_name="my-mbp",
    user_data=user_data_script,
    tags={"Name": "db-instance"},
    opts=pulumi.ResourceOptions(depends_on=secret_version)
)

# Add an A record to the wiz.internal zone for this instance
dns_record = aws.route53.Record("myInstanceRecord",
    zone_id=private_zone.id,
    name=f"{db_instance_name}.{internal_domain}",
    type="A",
    ttl=60,
    records=[db_instance.private_ip],  # Use the instance's private IP
    opts=pulumi.ResourceOptions(depends_on=[db_instance]),
)

pulumi.export("db_instance_public_dns", db_instance.public_dns)
# pulumi.export("user-data", user_data_script)