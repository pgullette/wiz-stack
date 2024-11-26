import pulumi
import json
import pulumi_aws as aws
from network import public_subnet_a, vpc

# AMI Lookup
ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["amazon"],
    filters=[{"name": "name", "values": ["amzn2-ami-hvm-*-x86_64-gp2"]}]
)

# Create an EC2 Instance (db-instance)
ec2_instance_profile = aws.iam.InstanceProfile(
    "ec2-instance-profile",
    role=aws.iam.Role(
        "ec2-instance-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"}
                }
            ]
        }),
        managed_policy_arns=["arn:aws:iam::aws:policy/AmazonEC2FullAccess"]
    )
)

db_instance_sg = aws.ec2.SecurityGroup(
    "db-instance-sg",
    vpc_id=vpc.id,
    description="Security Group for db-instance"
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

db_instance = aws.ec2.Instance(
    "db-instance",
    ami=ami.id,
    instance_type="t3.medium",
    subnet_id=public_subnet_a.id,
    vpc_security_group_ids=[db_instance_sg.id],
    iam_instance_profile=ec2_instance_profile.name,
    key_name="my-mbp",
    tags={"Name": "db-instance"}
)

pulumi.export("db_instance_public_dns", db_instance.public_dns)