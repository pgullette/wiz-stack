import pulumi
import pulumi_aws as aws
import json

# Create a VPC
vpc = aws.ec2.Vpc(
    "vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    enable_dns_support=True
)

# Create Public Subnets in two different AZs
public_subnet_a = aws.ec2.Subnet(
    "public-subnet-a",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    map_public_ip_on_launch=True,
    availability_zone="us-east-1a",
    tags={"Name": "public-subnet-a"}
)

public_subnet_b = aws.ec2.Subnet(
    "public-subnet-b",
    vpc_id=vpc.id,
    cidr_block="10.0.2.0/24",
    map_public_ip_on_launch=True,
    availability_zone="us-east-1b",
    tags={"Name": "public-subnet-b"}
)

# Create Private Subnets in two different AZs
private_subnet_a = aws.ec2.Subnet(
    "private-subnet-a",
    vpc_id=vpc.id,
    cidr_block="10.0.10.0/24",
    map_public_ip_on_launch=False,
    availability_zone="us-east-1a",
    tags={"Name": "private-subnet-a", "kubernetes.io/role/internal-elb": "1"}
)

private_subnet_b = aws.ec2.Subnet(
    "private-subnet-b",
    vpc_id=vpc.id,
    cidr_block="10.0.11.0/24",
    map_public_ip_on_launch=False,
    availability_zone="us-east-1b",
    tags={"Name": "private-subnet-b", "kubernetes.io/role/internal-elb": "1"}
)

# Internet Gateway for Public Subnet
igw = aws.ec2.InternetGateway("internet-gateway", vpc_id=vpc.id)

# Route Table for Public Subnet
public_route_table = aws.ec2.RouteTable(
    "public-route-table",
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block="0.0.0.0/0",
        gateway_id=igw.id
    )]
)

# Associate Public Subnets with Public Route Table
aws.ec2.RouteTableAssociation(
    "public-subnet-a-association",
    route_table_id=public_route_table.id,
    subnet_id=public_subnet_a.id
)

aws.ec2.RouteTableAssociation(
    "public-subnet-b-association",
    route_table_id=public_route_table.id,
    subnet_id=public_subnet_b.id
)

# Create an Elastic IP for NAT Gateway
nat_eip = aws.ec2.Eip("nat-eip", domain="vpc")

# Create NAT Gateway in the Public Subnet
nat_gateway = aws.ec2.NatGateway(
    "nat-gateway",
    subnet_id=public_subnet_a.id,
    allocation_id=nat_eip.id
)

# Route Table for Private Subnet with NAT Gateway
private_route_table = aws.ec2.RouteTable(
    "private-route-table",
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block="0.0.0.0/0",
        nat_gateway_id=nat_gateway.id
    )]
)

# Associate Private Subnets with Private Route Table
aws.ec2.RouteTableAssociation(
    "private-subnet-a-association",
    route_table_id=private_route_table.id,
    subnet_id=private_subnet_a.id
)

aws.ec2.RouteTableAssociation(
    "private-subnet-b-association",
    route_table_id=private_route_table.id,
    subnet_id=private_subnet_b.id
)

# Retrieve the Amazon Linux 2 AMI for the us-east-1 region
ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["amazon"],  # Only consider Amazon-owned AMIs
    filters=[
        {"name": "name", "values": ["amzn2-ami-hvm-*-x86_64-gp2"]},  # Amazon Linux 2 AMIs
    ]
)

# Security Group for EKS Nodes
node_sg = aws.ec2.SecurityGroup("node-sg",
    vpc_id=vpc.id,
    egress=[
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": ["0.0.0.0/0"]
        }
    ],
    tags={"Name": "node-sg"})

# Add ingress rule to allow inter security group access
aws.ec2.SecurityGroupRule(
    "allow-sg-ingress-access",
    type="ingress",
    from_port=0,
    to_port=0,
    protocol="-1",
    security_group_id=node_sg.id,
    source_security_group_id=node_sg.id
)

# Create EKS Role
eks_role = aws.iam.Role(
    "eks-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "eks.amazonaws.com"}
            }
        ]
    }),
    tags={"Name": "eks-role"}
)

# Attach EKS cluster policy to EKS Role
aws.iam.RolePolicyAttachment("eks-cluster-eks-role",
    role=eks_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
)

# Create EKS Cluster
eks_cluster = aws.eks.Cluster(
    "eks-cluster",
    role_arn=eks_role.arn,
    vpc_config=aws.eks.ClusterVpcConfigArgs(
        subnet_ids=[private_subnet_a.id, private_subnet_b.id],
        security_group_ids=[node_sg.id]
    ),
    tags={"Name": "eks-cluster"}
)

# Add CoreDNS add-on
coredns_addon = aws.eks.Addon(
    "coreDNSAddon",
    cluster_name=eks_cluster.name,
    addon_name="coredns",
    resolve_conflicts_on_update="OVERWRITE",  # Options: OVERWRITE, NONE, PRESERVE
)

# Add kube-proxy add-on
kube_proxy_addon = aws.eks.Addon(
    "kubeProxyAddon",
    cluster_name=eks_cluster.name,
    addon_name="kube-proxy",
    resolve_conflicts_on_update="OVERWRITE",
)

# Add VPC CNI add-on
vpc_cni_addon = aws.eks.Addon(
    "vpcCNIAddon",
    cluster_name=eks_cluster.name,
    addon_name="vpc-cni",
    resolve_conflicts_on_update="OVERWRITE",
)

# Add EKS Pod Identity Agent add-on
eks_pod_identity_agent = aws.eks.Addon(
    "eks-pod-identity-agent",
    cluster_name=eks_cluster.name,
    addon_name="eks-pod-identity-agent",
    resolve_conflicts_on_update="OVERWRITE"
)

# Create Node Role
node_role = aws.iam.Role(
    "eks-node-role",
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
    tags={"Name": "eks-node-role"}
)

# Attach policies to the node role
# SSM
aws.iam.RolePolicyAttachment("node-role-ssm-managed",
    role=node_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
)

aws.iam.RolePolicyAttachment("eks-worker-node-policy",
    role=node_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
)

aws.iam.RolePolicyAttachment("eks-cni-policy",
    role=node_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
)

# ECR read-only access policy
aws.iam.RolePolicyAttachment("ecr-readonly-policy",
    role=node_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
)

# Create Node Group
node_group = aws.eks.NodeGroup(
    "eks-node-group",
    cluster_name=eks_cluster.name,
    node_role_arn=node_role.arn,
    subnet_ids=[private_subnet_a.id, private_subnet_b.id],
    scaling_config=aws.eks.NodeGroupScalingConfigArgs(
        desired_size=2,
        max_size=2,
        min_size=1
    ),
    instance_types=["t3.medium"]
)

# Load Balancer for EKS
load_balancer = aws.lb.LoadBalancer(
    "eks-load-balancer",
    internal=False,
    security_groups=[node_sg.id],
    subnets=[public_subnet_a.id, public_subnet_b.id]
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

# Output some items
pulumi.export("db-instance", db_instance.public_dns)
pulumi.export("eks-cluster", eks_cluster.endpoint)